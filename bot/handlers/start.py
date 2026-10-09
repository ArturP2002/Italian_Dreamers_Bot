import logging
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
    WebAppInfo,
)

from app.auth.telegram import TelegramWebAppUser, upsert_user_from_telegram
from app.config import get_settings
from app.database import async_session_factory
from app.services.referrals import claim_referral

logger = logging.getLogger(__name__)

router = Router(name="start")


def webapp_keyboard(url: str, language: str = "ru") -> InlineKeyboardMarkup:
    label = "Открыть Italian Dreamers" if language == "ru" else "Apri Italian Dreamers"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))],
        ]
    )


def _with_startapp(url: str, param: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}startapp={param}"


async def _register_referral(tg_user: User, code: str) -> None:
    settings = get_settings()
    try:
        async with async_session_factory() as session:
            user = await upsert_user_from_telegram(
                session,
                TelegramWebAppUser(
                    id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    last_name=tg_user.last_name,
                    language_code=tg_user.language_code,
                    is_premium=bool(tg_user.is_premium),
                ),
            )
            await claim_referral(session, settings, user=user, code=code)
    except Exception:
        logger.exception("Failed to register referral for %s", tg_user.id)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    settings = get_settings()
    lang = (message.from_user.language_code or "ru")[:2] if message.from_user else "ru"
    if lang not in {"ru", "it"}:
        lang = "ru"

    payload = (command.args or "").strip()
    if re.fullmatch(r"write_\d+", payload):
        if lang == "it":
            text = (
                "Scrivi una lettera a questo profilo 👇\n\n"
                "Hai già premuto «Avvia» — riceverai un avviso quando rispondono."
            )
            label = "✉️ Scrivi una lettera"
        else:
            text = (
                "Напишите письмо этой анкете 👇\n\n"
                "Вы уже нажали «Начать» — когда вам ответят, придёт уведомление в этот чат."
            )
            label = "✉️ Написать письмо"
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=label,
                            web_app=WebAppInfo(url=_with_startapp(settings.webapp_url, payload)),
                        )
                    ]
                ]
            ),
        )
        return

    if message.from_user and re.fullmatch(r"ref_[A-Za-z0-9_-]{1,32}", payload):
        await _register_referral(message.from_user, payload[len("ref_"):])

    if payload == "notify":
        if lang == "it":
            text = (
                "✅ Perfetto. Ora il bot può inviarti notifiche "
                "(nuove lettere, risposte, pagamento).\n\n"
                "Apri l’app qui sotto."
            )
        else:
            text = (
                "✅ Готово. Теперь бот может присылать уведомления "
                "(новые письма, ответы, оплата).\n\n"
                "Откройте приложение кнопкой ниже."
            )
        await message.answer(text, reply_markup=webapp_keyboard(settings.webapp_url, language=lang))
        return

    if lang == "it":
        text = (
            "<b>Italian Dreamers</b>\n\n"
            "Benvenuto. Tutto avviene nell'app: profilo, lettere, chat.\n"
            "Premendo «Avvia» attivi anche le notifiche push del bot.\n"
            "Tocca il pulsante qui sotto per entrare."
        )
    else:
        text = (
            "<b>Italian Dreamers</b>\n\n"
            "Добро пожаловать. Анкета, письма и чат — в Mini App.\n"
            "Нажав «Начать», вы также включаете push-уведомления от бота.\n"
            "Нажмите кнопку ниже, чтобы войти."
        )

    await message.answer(
        text,
        reply_markup=webapp_keyboard(settings.webapp_url, language=lang),
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    settings = get_settings()
    if not message.from_user or not settings.is_admin(message.from_user.id):
        return
    url = _with_startapp(settings.webapp_url, "admin")
    await message.answer(
        "Админ-панель ↓",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Открыть админку", web_app=WebAppInfo(url=url))]]
        ),
    )


@router.message(F.text == "/app")
async def cmd_app(message: Message) -> None:
    settings = get_settings()
    await message.answer(
        "Mini App ↓",
        reply_markup=webapp_keyboard(settings.webapp_url),
    )
