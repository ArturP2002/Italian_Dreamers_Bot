import logging
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    User,
    WebAppInfo,
)
from sqlalchemy import select

from app.auth.telegram import TelegramWebAppUser, upsert_user_from_telegram
from app.config import get_settings
from app.database import async_session_factory
from app.models import User as DbUser
from app.services.referrals import claim_referral

logger = logging.getLogger(__name__)

router = Router(name="start")

LANG_CALLBACK_PREFIX = "lang:"


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


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Русский", callback_data=f"{LANG_CALLBACK_PREFIX}ru"),
                InlineKeyboardButton(text="Italiano", callback_data=f"{LANG_CALLBACK_PREFIX}it"),
            ]
        ]
    )


def _with_startapp(url: str, param: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}startapp={param}"


def _normalize_lang(code: str | None) -> str:
    lang = (code or "ru")[:2].lower()
    return lang if lang in {"ru", "it"} else "ru"


def _tg_user_payload(tg_user: User) -> TelegramWebAppUser:
    return TelegramWebAppUser(
        id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
        language_code=tg_user.language_code,
        is_premium=bool(tg_user.is_premium),
    )


async def _resolve_lang(tg_user: User | None) -> str:
    """Prefer language saved in DB (Mini App / bot picker), else Telegram client lang."""
    if tg_user is None:
        return "ru"
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(DbUser).where(DbUser.telegram_id == tg_user.id))
            user = result.scalar_one_or_none()
            if user is not None and user.language_code in {"ru", "it"}:
                return user.language_code
    except Exception:
        logger.exception("Failed to resolve language for %s", tg_user.id)
    return _normalize_lang(tg_user.language_code)


async def _save_lang(tg_user: User, lang: str) -> str:
    lang = _normalize_lang(lang)
    settings = get_settings()
    try:
        async with async_session_factory() as session:
            await upsert_user_from_telegram(
                session,
                _tg_user_payload(tg_user),
                preferred_language=lang,
            )
    except Exception:
        logger.exception("Failed to save language for %s", tg_user.id)
    return lang


async def _register_referral(tg_user: User, code: str) -> None:
    settings = get_settings()
    try:
        async with async_session_factory() as session:
            user = await upsert_user_from_telegram(session, _tg_user_payload(tg_user))
            await claim_referral(session, settings, user=user, code=code)
    except Exception:
        logger.exception("Failed to register referral for %s", tg_user.id)


def _welcome_text(lang: str, channel_url: str) -> str:
    if lang == "it":
        return (
            "<b>Italian Dreamers</b>\n\n"
            "Questo è il bot del canale Italian Dreamers.\n"
            "Profilo → verifica → pagamento → pubblicazione sul canale e nell'app.\n\n"
            "Mentre aspetti la moderazione, dai un'occhiata al canale — la community "
            f"è già attiva:\n{channel_url}\n\n"
            "Tocca il pulsante qui sotto per aprire l'app."
        )
    return (
        "<b>Italian Dreamers</b>\n\n"
        "Это бот канала Italian Dreamers.\n"
        "Анкета → проверка → оплата → публикация в канале и в приложении.\n\n"
        "Пока ждёте модерацию — загляните в канал, там уже живое комьюнити:\n"
        f"{channel_url}\n\n"
        "Нажмите кнопку ниже, чтобы открыть приложение."
    )


async def _send_welcome(message: Message, lang: str) -> None:
    settings = get_settings()
    channel_url = settings.channel_url.strip() or "https://t.me/italiandreamers"
    await message.answer(
        _welcome_text(lang, channel_url),
        reply_markup=webapp_keyboard(
            settings.webapp_url,
            language=lang,
            channel_url=channel_url,
        ),
        disable_web_page_preview=True,
    )


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    settings = get_settings()
    lang = await _resolve_lang(message.from_user)

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
        await _register_referral(message.from_user, payload[len("ref_") :])

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

    # First step: explicit language choice (RU / IT), then welcome in that language.
    if lang == "it":
        prompt = "Scegli la lingua / Выберите язык:"
    else:
        prompt = "Выберите язык / Scegli la lingua:"
    await message.answer(prompt, reply_markup=language_keyboard())


@router.callback_query(F.data.startswith(LANG_CALLBACK_PREFIX))
async def on_language_chosen(query: CallbackQuery) -> None:
    raw = (query.data or "")[len(LANG_CALLBACK_PREFIX) :]
    lang = _normalize_lang(raw)
    if query.from_user is None:
        await query.answer()
        return
    await _save_lang(query.from_user, lang)
    await query.answer()
    if query.message is not None:
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await _send_welcome(query.message, lang)


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    settings = get_settings()
    if not message.from_user or not settings.is_admin(message.from_user.id):
        return
    lang = await _resolve_lang(message.from_user)
    url = _with_startapp(settings.webapp_url, "admin")
    text = "Pannello admin ↓" if lang == "it" else "Админ-панель ↓"
    btn = "Apri admin" if lang == "it" else "Открыть админку"
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=btn, web_app=WebAppInfo(url=url))]]
        ),
    )


@router.message(F.text == "/app")
async def cmd_app(message: Message) -> None:
    settings = get_settings()
    lang = await _resolve_lang(message.from_user)
    text = "Mini App ↓" if lang == "it" else "Mini App ↓"
    await message.answer(
        text,
        reply_markup=webapp_keyboard(settings.webapp_url, language=lang),
    )
