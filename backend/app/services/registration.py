"""Registration + starter gift helpers (Plus-only model)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, ProfileStatus, User
from app.services.entitlements import has_unlimited

REGISTERED_STATUSES = {
    ProfileStatus.QUEUED.value,
    ProfileStatus.PUBLISHED.value,
}


def profile_is_registered(profile: Profile | None) -> bool:
    """Catalog-visible registration (queued/published). Plus may still be required separately."""
    if profile is None:
        return False
    return profile.status in REGISTERED_STATUSES


async def user_is_registered(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    return profile_is_registered(result.scalar_one_or_none())


async def user_can_use_app(session: AsyncSession, user_id: int) -> bool:
    """Active Dreamers Plus — full write/read/catalog presence."""
    return await has_unlimited(session, user_id)


async def grant_starter_gifts(session: AsyncSession, user: User) -> bool:
    """Give 3 gift conversations once. Does NOT add message_credits (Plus-only)."""
    if user.gift_credits_granted:
        return False
    user.gift_credits_granted = True
    user.gift_credits_left = 3
    session.add(user)
    return True


async def grant_registration_bonus(session: AsyncSession, user: User) -> bool:
    """Legacy no-op under Plus-only (kept for call sites)."""
    if user.registration_bonus_granted:
        return False
    user.registration_bonus_granted = True
    session.add(user)
    return True


def consume_gift_marker(user: User) -> bool:
    """Spend one gift conversation slot. Returns True if a gift was consumed."""
    if (user.gift_credits_left or 0) > 0:
        user.gift_credits_left -= 1
        return True
    return False


def gifts_remaining(user: User) -> int:
    return max(0, int(user.gift_credits_left or 0))
