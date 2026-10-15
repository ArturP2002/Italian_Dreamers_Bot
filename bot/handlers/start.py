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


def webapp_keyboard(
    url: str,
    language: str = "ru",
    *,
    channel_url: str | None = None,
) -> InlineKeyboardMarkup:
    label = "Открыть Italian Dreamers" if language == "ru" else "Apri Italian Dreamers"
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))],
    ]
    if channel_url:
        channel_label = "Перейти в канал" if language == "ru" else "Vai al canale"
        rows.append([InlineKeyboardButton(text=channel_label, url=channel_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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

    channel_url = settings.channel_url.strip() or "https://t.me/italiandreamers"
    if lang == "it":
        text = (
            "<b>Italian Dreamers</b>\n\n"
            "Questo è il bot del canale Italian Dreamers.\n"
            "Profilo → verifica → pagamento → pubblicazione sul canale e nell'app.\n\n"
            "Mentre aspetti la moderazione, dai un'occhiata al canale — la community "
            f"è già attiva:\n{channel_url}\n\n"
            "Tocca il pulsante qui sotto per aprire l'app."
        )
    else:
        text = (
            "<b>Italian Dreamers</b>\n\n"
            "Это бот канала Italian Dreamers.\n"
            "Анкета → проверка → оплата → публикация в канале и в приложении.\n\n"
            "Пока ждёте модерацию — загляните в канал, там уже живое комьюнити:\n"
            f"{channel_url}\n\n"
            "Нажмите кнопку ниже, чтобы открыть приложение."
        )

    await message.answer(
        text,
        reply_markup=webapp_keyboard(
            settings.webapp_url,
            language=lang,
            channel_url=channel_url,
        ),
        disable_web_page_preview=True,
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
