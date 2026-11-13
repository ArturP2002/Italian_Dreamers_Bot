"""Paid registration gate helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, ProfileStatus, User

REGISTERED_STATUSES = {
    ProfileStatus.QUEUED.value,
    ProfileStatus.PUBLISHED.value,
}


def profile_is_registered(profile: Profile | None) -> bool:
    if profile is None:
        return False
    return profile.status in REGISTERED_STATUSES


async def user_is_registered(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    return profile_is_registered(result.scalar_one_or_none())


async def grant_starter_gifts(session: AsyncSession, user: User) -> bool:
    """Give 3 message credits once on first app entry. Returns True if granted now."""
    if user.gift_credits_granted:
        return False
    from app.models import CreditLedgerEntry, LedgerEntryType

    user.gift_credits_granted = True
    user.gift_credits_left = 3
    user.message_credits = (user.message_credits or 0) + 3
    session.add(user)
    session.add(
        CreditLedgerEntry(
            user_id=user.id,
            entry_type=LedgerEntryType.ADMIN_GRANT.value,
            delta=3,
            balance_after=user.message_credits,
            note="starter_gifts_3",
        )
    )
    return True


async def grant_registration_bonus(session: AsyncSession, user: User) -> bool:
    """+1 credit after paid publish registration."""
    if user.registration_bonus_granted:
        return False
    from app.models import CreditLedgerEntry, LedgerEntryType

    user.registration_bonus_granted = True
    user.message_credits = (user.message_credits or 0) + 1
    session.add(user)
    session.add(
        CreditLedgerEntry(
            user_id=user.id,
            entry_type=LedgerEntryType.ADMIN_GRANT.value,
            delta=1,
            balance_after=user.message_credits,
            note="registration_bonus",
        )
    )
    return True


def consume_gift_marker(user: User) -> bool:
    """Mark one spend as coming from starter gifts. Returns True if still in gift pool."""
    if (user.gift_credits_left or 0) > 0:
        user.gift_credits_left -= 1
        return True
    return False
