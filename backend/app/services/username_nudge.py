"""Username is optional on submit; bot reminds twice with instruction photos."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.database import async_session_factory
from app.models import Profile, ProfileStatus, User
from app.services.telegram_api import get_chat, send_photo_file

logger = logging.getLogger(__name__)

HOWTO_DIR = Path(__file__).resolve().parents[2] / "username_howto"
CHECK_CALLBACK = "uname:check"

NUDGE_TEXT = {
    "ru": (
        "Чтобы после знакомства вы могли перейти в личный чат, нужно имя пользователя "
        "в Telegram (ник со знаком @). Сейчас у тебя его нет. Создай по картинке — "
        "это 1 минута, потом нажми кнопку ниже 👇"
    ),
    "it": (
        "Per passare alla chat privata dopo la conoscenza ti serve uno username su Telegram "
        "(il nickname con la @). Per ora non ce l'hai. Crealo seguendo l'immagine — "
        "è 1 minuto, poi tocca il pulsante qui sotto 👇"
    ),
}

CHECK_BUTTON = {"ru": "✅ Проверить", "it": "✅ Verifica"}
OK_TEXT = {
    "ru": "Готово! Твой ник @{username} сохранён в анкете ✅",
    "it": "Fatto! Il tuo username @{username} è salvato nel profilo ✅",
}
MISS_TEXT = {
    "ru": "Пока не вижу ника 🙈 Проверь, что нажала «Готово» в настройках, и попробуй ещё раз.",
    "it": "Non vedo ancora lo username 🙈 Controlla di aver toccato «Fine» nelle impostazioni e riprova.",
}


def _lang(user: User) -> str:
    return user.language_code if user.language_code in {"ru", "it"} else "ru"


def howto_paths(platform: str | None, lang: str) -> list[Path]:
    lang = lang if lang in {"ru", "it"} else "ru"
    plat = (platform or "").lower()
    if plat in {"ios", "iphone", "macos"}:
        names = [f"iphone_{lang}.jpg"]
    elif plat in {"android", "android_x"}:
        names = [f"android_{lang}.jpg"]
    else:
        names = [f"iphone_{lang}.jpg", f"android_{lang}.jpg"]
    return [p for name in names if (p := HOWTO_DIR / name).is_file()]


def normalize_username(value: str | None) -> str | None:
    if not value:
        return None
    clean = value.strip().lstrip("@")
    return clean or None


def apply_username(user: User, profile: Profile | None, username: str) -> None:
    user.telegram_username = username
    if profile is not None:
        profile.telegram_username = username


async def fetch_telegram_username(settings: Settings, telegram_id: int) -> str | None:
    try:
        payload = await get_chat(settings, telegram_id)
    except Exception:
        logger.exception("getChat failed for %s", telegram_id)
        return None
    result = payload.get("result") or {}
    return normalize_username(result.get("username"))


def _markup(lang: str) -> dict:
    return {"inline_keyboard": [[{"text": CHECK_BUTTON[lang], "callback_data": CHECK_CALLBACK}]]}


async def send_username_nudge(settings: Settings, *, user: User, round_number: int) -> bool:
    lang = _lang(user)
    paths = howto_paths(user.telegram_platform, lang)
    caption = NUDGE_TEXT[lang]
    markup = _markup(lang)
    if not paths:
        from app.services.telegram_api import send_message

        try:
            await send_message(settings, user.telegram_id, caption, reply_markup=markup)
            return True
        except Exception:
            logger.exception("Failed username nudge text for %s", user.telegram_id)
            return False
    try:
        first, *rest = paths
        await send_photo_file(
            settings, user.telegram_id, first, caption=caption, reply_markup=markup
        )
        for extra in rest:
            await send_photo_file(settings, user.telegram_id, extra)
        return True
    except Exception:
        logger.exception("Failed username nudge photo (round %s) for %s", round_number, user.telegram_id)
        return False


async def maybe_nudge_after_submit(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    profile: Profile,
) -> None:
    username = normalize_username(profile.telegram_username) or normalize_username(user.telegram_username)
    if username:
        apply_username(user, profile, username)
        session.add(user)
        session.add(profile)
        await session.commit()
        return
    now = datetime.now(timezone.utc)
    if user.username_nudge_sent_at is None:
        ok = await send_username_nudge(settings, user=user, round_number=1)
        if ok:
            user.username_nudge_sent_at = now
            session.add(user)
            await session.commit()


async def process_username_nudges(settings: Settings) -> int:
    """Second reminder 24h after the first, if username is still missing."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    sent = 0
    async with async_session_factory() as session:
        result = await session.execute(
            select(User)
            .outerjoin(Profile, Profile.user_id == User.id)
            .where(
                User.username_nudge_sent_at.is_not(None),
                User.username_nudge_sent_at <= cutoff,
                User.username_nudge_2_at.is_(None),
                or_(User.telegram_username.is_(None), User.telegram_username == ""),
                or_(
                    Profile.id.is_(None),
                    Profile.status.notin_(
                        [ProfileStatus.HIDDEN.value, ProfileStatus.REJECTED.value]
                    ),
                ),
            )
            .options(selectinload(User.profile))
            .limit(30)
        )
        users = list(result.scalars().all())
        for user in users:
            profile = user.profile
            if profile and normalize_username(profile.telegram_username):
                apply_username(user, profile, profile.telegram_username or "")
                session.add(user)
                continue
            if profile and profile.status in {
                ProfileStatus.HIDDEN.value,
                ProfileStatus.REJECTED.value,
            }:
                continue
            ok = await send_username_nudge(settings, user=user, round_number=2)
            if ok:
                user.username_nudge_2_at = datetime.now(timezone.utc)
                session.add(user)
                sent += 1
        await session.commit()
    return sent


async def check_and_store_username(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
) -> str | None:
    username = await fetch_telegram_username(settings, user.telegram_id)
    if not username:
        return None
    result = await session.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    apply_username(user, profile, username)
    session.add(user)
    if profile is not None:
        session.add(profile)
    await session.commit()
    await session.refresh(user)
    return username
