"""Admin-only /broadcast_moderation — notify users waiting on profile moderation."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from aiogram import Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import async_session_factory
from app.models import Gender, Profile, ProfileStatus, User

logger = logging.getLogger(__name__)

router = Router(name="broadcast")

TEXT_RU = (
    "Привет! ❤️\n"
    "Твоя анкета уже у нас и пока находится на модерации! 😊\n"
    "Наше мини-приложение было создано совсем недавно, и мы планируем запустить его "
    "примерно через 2–3 недели. Как только оно заработает, я одобрю твою анкету, и она "
    "сразу появится в нашем новом мини-приложении, а чуть позже мы опубликуем её ещё и "
    "в нашем Telegram-канале! 🥰\n"
    "И, кстати, именно в наш канал я очень хочу тебя пригласить уже сейчас! "
    "Он совершенно бесплатный! ❤️\n"
    "Нашему каналу Italian Dreamers уже 6 месяцев, и жизнь там давно кипит вовсю! 🇮🇹 "
    "У нас уже сформировалось большое и очень классное комьюнити! Каждый день публикуются "
    "анкеты мужчин и женщин, люди общаются, знакомятся и находят друг друга. И у нас уже "
    "есть много счастливых пар, которые познакомились именно здесь! ❤️\n"
    "Можно писать в личные сообщения понравившимся мужчинам, а каждую пятницу у нас "
    "проходит день знакомств в комментариях! Можно оставлять свои фотографии, немного "
    "рассказывать о себе и знакомиться прямо там.\n"
    "Так что жди сообщения об одобрении твоей анкеты, как только мы закончим подготовку "
    "мини-приложения. А пока добро пожаловать в Italian Dreamers! 🇮🇹❤️\n"
    "👉 Вот ссылка на наш канал: {channel_url}\n"
    "Желаю тебе найти именно того, кого ты ищешь!"
)

TEXT_IT = (
    "Ciao! ❤️\n"
    "Il tuo profilo è già arrivato ed è attualmente in fase di approvazione! 😊\n"
    "La nostra mini-app è stata creata da pochissimo e prevediamo di lanciarla tra circa "
    "2–3 settimane. Non appena sarà attiva, approverò il tuo profilo, che apparirà subito "
    "nella nostra nuova mini-app e, poco dopo, lo pubblicheremo anche sul nostro canale "
    "Telegram! 🥰\n"
    "E, a proposito, mi piacerebbe tantissimo invitarti a entrare nel nostro canale già da "
    "adesso! È completamente gratuito! ❤️\n"
    "Il nostro canale Italian Dreamers esiste già da 6 mesi e lì la vita è in pieno "
    "fermento! 🇮🇹 Abbiamo già creato una community grande e davvero bellissima! Ogni "
    "giorno pubblichiamo i profili di uomini e donne, le persone chiacchierano, si "
    "conoscono e si incontrano. E abbiamo già tante coppie felici che si sono conosciute "
    "proprio grazie a noi! ❤️\n"
    "Puoi scrivere in privato alle donne che ti piacciono e ogni venerdì organizziamo una "
    "giornata dedicata alle conoscenze nei commenti! Puoi lasciare le tue foto, raccontare "
    "qualcosa di te e conoscere nuove persone direttamente lì.\n"
    "Quindi, aspetta il messaggio di approvazione del tuo profilo non appena avremo "
    "terminato la preparazione della mini-app. Nel frattempo, benvenuto su Italian "
    "Dreamers! 🇮🇹❤️\n"
    "👉 Ecco il link al nostro canale: {channel_url}\n"
    "Ti auguro di trovare proprio la persona che stai cercando!"
)


@dataclass(frozen=True)
class BroadcastTarget:
    profile_id: int
    telegram_id: int
    lang: str


def _message_lang(profile: Profile, user: User) -> str:
    gender = (profile.gender or user.gender or "").strip().lower()
    if gender == Gender.FEMALE.value:
        return "ru"
    if gender == Gender.MALE.value:
        return "it"
    code = (user.language_code or "ru")[:2].lower()
    return "it" if code == "it" else "ru"


def _channel_keyboard(channel_url: str, lang: str) -> InlineKeyboardMarkup:
    label = "Перейти в канал" if lang == "ru" else "Vai al canale"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, url=channel_url)]]
    )


def _waiting_base_query():
    return (
        select(Profile)
        .join(User, Profile.user_id == User.id)
        .where(
            Profile.status == ProfileStatus.NEW.value,
            User.is_blocked.is_(False),
        )
        .options(selectinload(Profile.user))
    )


async def _load_eligible() -> list[BroadcastTarget]:
    async with async_session_factory() as session:
        result = await session.execute(
            _waiting_base_query().where(Profile.moderation_waiting_notified_at.is_(None))
        )
        profiles = list(result.scalars().all())
        return [
            BroadcastTarget(
                profile_id=p.id,
                telegram_id=p.user.telegram_id,
                lang=_message_lang(p, p.user),
            )
            for p in profiles
        ]


async def _count_stats() -> tuple[int, int, int, int]:
    """Return (to_send, already_notified, to_send_ru, to_send_it)."""
    async with async_session_factory() as session:
        already = await session.scalar(
            select(func.count())
            .select_from(Profile)
            .join(User, Profile.user_id == User.id)
            .where(
                Profile.status == ProfileStatus.NEW.value,
                User.is_blocked.is_(False),
                Profile.moderation_waiting_notified_at.is_not(None),
            )
        )
        result = await session.execute(
            _waiting_base_query().where(Profile.moderation_waiting_notified_at.is_(None))
        )
        profiles = list(result.scalars().all())

    ru = it = 0
    for p in profiles:
        if _message_lang(p, p.user) == "it":
            it += 1
        else:
            ru += 1
    return len(profiles), int(already or 0), ru, it


def _is_admin(message: Message) -> bool:
    settings = get_settings()
    return bool(message.from_user and settings.is_admin(message.from_user.id))


@router.message(Command("broadcast_moderation"))
async def cmd_broadcast_moderation(message: Message, command: CommandObject) -> None:
    if not _is_admin(message):
        return

    args = (command.args or "").strip().lower()
    if args == "confirm":
        await _run_broadcast(message)
        return

    to_send, already, ru, it = await _count_stats()
    await message.answer(
        "<b>Рассылка ждущим модерации</b>\n\n"
        f"К отправке: <b>{to_send}</b> (RU {ru} · IT {it})\n"
        f"Уже уведомлены (пропуск): <b>{already}</b>\n\n"
        "Чтобы отправить: <code>/broadcast_moderation confirm</code>"
    )


async def _run_broadcast(message: Message) -> None:
    settings = get_settings()
    channel_url = settings.channel_url.strip() or "https://t.me/italiandreamers"
    targets = await _load_eligible()
    if not targets:
        await message.answer("Некому отправлять: нет анкет new без уведомления.")
        return

    await message.answer(f"Начинаю рассылку: {len(targets)} получателей…")

    sent = 0
    errors = 0
    for target in targets:
        text_tpl = TEXT_IT if target.lang == "it" else TEXT_RU
        text = text_tpl.format(channel_url=channel_url)
        keyboard = _channel_keyboard(channel_url, target.lang)
        try:
            await message.bot.send_message(
                chat_id=target.telegram_id,
                text=text,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 0.5)
            try:
                await message.bot.send_message(
                    chat_id=target.telegram_id,
                    text=text,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            except Exception:
                errors += 1
                logger.exception("Broadcast failed after retry for %s", target.telegram_id)
                await asyncio.sleep(0.05)
                continue
        except TelegramForbiddenError:
            errors += 1
            logger.info("Broadcast forbidden for %s (blocked bot)", target.telegram_id)
            await asyncio.sleep(0.05)
            continue
        except Exception:
            errors += 1
            logger.exception("Broadcast failed for %s", target.telegram_id)
            await asyncio.sleep(0.05)
            continue

        async with async_session_factory() as session:
            profile = await session.get(Profile, target.profile_id)
            if profile is not None and profile.moderation_waiting_notified_at is None:
                profile.moderation_waiting_notified_at = datetime.now(timezone.utc)
                await session.commit()
        sent += 1
        await asyncio.sleep(0.06)

    await message.answer(
        f"Готово.\nОтправлено: <b>{sent}</b>\nОшибки: <b>{errors}</b>\n"
        f"Всего в этой волне: {len(targets)}"
    )
