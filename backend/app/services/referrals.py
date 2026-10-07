"""Referral codes: shareable bot links, one-time claim, referrer notification."""

from __future__ import annotations

import logging
import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import CreditLedgerEntry, LedgerEntryType, User
from app.services.notify import notify_referrer_joined
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
        # Without a Main Mini App, ?startapp only opens the chat; ?start reaches /start.
        return f"https://t.me/{username}?start=ref_{code}"
    return f"{settings.webapp_url.rstrip('/')}/?startapp=ref_{code}"


async def count_invited(session: AsyncSession, user: User) -> int:
    result = await session.execute(
        select(func.count()).select_from(User).where(User.referred_by_user_id == user.id)
    )
    return int(result.scalar_one())


async def claim_referral(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    code: str,
) -> bool:
    """Attach `user` to the owner of `code` once; returns True when newly attached."""
    cleaned = (code or "").strip()
    if not cleaned or user.referred_by_user_id:
        return False
    result = await session.execute(select(User).where(User.referral_code == cleaned))
    referrer = result.scalar_one_or_none()
    if referrer is None or referrer.id == user.id:
        return False
    user.referred_by_user_id = referrer.id
    session.add(user)
    bonus = max(0, settings.referral_bonus_credits)
    if bonus:
        referrer.message_credits += bonus
        session.add(referrer)
        session.add(
            CreditLedgerEntry(
                user_id=referrer.id,
                entry_type=LedgerEntryType.REFERRAL.value,
                delta=bonus,
                balance_after=referrer.message_credits,
                note=f"referral:{user.id}",
            )
        )
    await session.commit()
    await session.refresh(user)
    await session.refresh(referrer)
    try:
        await notify_referrer_joined(
            settings,
            referrer=referrer,
            invited=user,
            total=await count_invited(session, referrer),
            bonus=bonus,
        )
    except Exception:
        logger.exception("Failed to notify referrer %s", referrer.telegram_id)
    return True
