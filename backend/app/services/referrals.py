"""Referral codes: shareable bot links, one-time claim; top days on friend's Plus."""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import User
from app.services.entitlements import apply_top_until, utcnow
from app.services.notify import notify_referrer_joined
from app.services.profiles import get_user_profile
from app.services.telegram_api import get_bot_info

logger = logging.getLogger(__name__)


def ensure_referral_code(user: User) -> str:
    if user.referral_code:
        return user.referral_code
    user.referral_code = secrets.token_urlsafe(8)[:12]
    return user.referral_code


async def referral_link(settings: Settings, code: str) -> str:
    info = await get_bot_info(settings)
    username = info.get("username")
    if username and info.get("has_main_web_app"):
        return f"https://t.me/{username}?startapp=ref_{code}"
    if username:
        return f"https://t.me/{username}?start=ref_{code}"
    return f"{settings.webapp_url.rstrip('/')}/?startapp=ref_{code}"


async def count_invited(session: AsyncSession, user: User) -> int:
    result = await session.execute(
        select(func.count()).select_from(User).where(User.referred_by_user_id == user.id)
    )
    return int(result.scalar_one())


async def count_plus_invited(session: AsyncSession, user: User) -> int:
    """Friends who joined via link AND already bought Plus (rewarded)."""
    result = await session.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.referred_by_user_id == user.id,
            User.referral_plus_rewarded.is_(True),
        )
    )
    return int(result.scalar_one())


def referral_top_days_for_invites(settings: Settings, plus_invited_count: int) -> int:
    days = max(0, settings.referral_bonus_top_days)
    return max(0, plus_invited_count) * days


async def claim_referral(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    code: str,
) -> bool:
    """Attach `user` to the owner of `code` once. Top days are granted on Plus, not here."""
    cleaned = (code or "").strip()
    if not cleaned or user.referred_by_user_id:
        return False
    result = await session.execute(select(User).where(User.referral_code == cleaned))
    referrer = result.scalar_one_or_none()
    if referrer is None or referrer.id == user.id:
        return False
    user.referred_by_user_id = referrer.id
    session.add(user)
    await session.commit()
    await session.refresh(user)
    await session.refresh(referrer)
    try:
        await notify_referrer_joined(
            settings,
            referrer=referrer,
            invited=user,
            total=await count_invited(session, referrer),
            bonus=0,
            top_days=0,
        )
    except Exception:
        logger.exception("Failed to notify referrer %s", referrer.telegram_id)
    return True


async def reward_referrer_on_plus(
    session: AsyncSession,
    settings: Settings,
    *,
    payer: User,
) -> bool:
    """When a referred friend buys Plus — grant stacked top days to referrer once."""
    if payer.referral_plus_rewarded or not payer.referred_by_user_id:
        return False
    top_days = max(0, settings.referral_bonus_top_days)
    result = await session.execute(select(User).where(User.id == payer.referred_by_user_id))
    referrer = result.scalar_one_or_none()
    if referrer is None:
        payer.referral_plus_rewarded = True
        session.add(payer)
        return False
    if top_days:
        profile = await get_user_profile(session, referrer.id)
        if profile is not None:
            now = utcnow()
            base = profile.top_until if profile.top_until and profile.top_until > now else now
            apply_top_until(profile, base + timedelta(days=top_days))
            session.add(profile)
    payer.referral_plus_rewarded = True
    session.add(payer)
    session.add(referrer)
    try:
        await notify_referrer_joined(
            settings,
            referrer=referrer,
            invited=payer,
            total=await count_plus_invited(session, referrer) + 1,
            bonus=0,
            top_days=top_days,
        )
    except Exception:
        logger.exception("Failed Plus-referral notify %s", referrer.telegram_id)
    return True
