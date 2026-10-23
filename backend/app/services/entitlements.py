"""Unlimited subscription and catalog-top helpers. Gate by expires_at, not Stars charge id."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, Subscription, SubscriptionStatus

SUBSCRIPTION_PERIOD = timedelta(days=30)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def active_subscription(session: AsyncSession, user_id: int) -> Subscription | None:
    now = utcnow()
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def has_unlimited(session: AsyncSession, user_id: int) -> bool:
    return (await active_subscription(session, user_id)) is not None


def is_top_now(profile: Profile, now: datetime | None = None) -> bool:
    now = now or utcnow()
    return bool(profile.top_until and profile.top_until > now)


def extend_datetime(current: datetime | None, until: datetime) -> datetime:
    if current is None or current < until:
        return until
    return current


def apply_top_until(profile: Profile, until: datetime) -> None:
    profile.top_until = extend_datetime(profile.top_until, until)


async def apply_top_for_user(session: AsyncSession, user_id: int, until: datetime) -> Profile | None:
    result = await session.execute(select(Profile).where(Profile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        return None
    apply_top_until(profile, until)
    session.add(profile)
    return profile
