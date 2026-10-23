"""Remind unpaid approved profiles on days 3/14/27 and delete on day 30."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.database import async_session_factory
from app.models import Profile, ProfileStatus
from app.services.notify import notify_unpaid_deleted, notify_unpaid_reminder
from app.services.takedown import _profile_files

logger = logging.getLogger(__name__)

REMINDER_DAYS = (3, 14, 27)
DELETE_AFTER_DAYS = 30


def _anchor(profile: Profile) -> datetime | None:
    stamp = profile.approved_at or profile.updated_at
    if stamp is None:
        return None
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp


async def delete_unpaid_profile(
    session: AsyncSession,
    settings: Settings,
    *,
    profile: Profile,
) -> None:
    owner = profile.user
    files = await _profile_files(session, profile)
    name = profile.name
    await session.delete(profile)
    await session.commit()
    for path in files:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to delete unpaid-profile file %s", path)
    if owner is not None:
        await notify_unpaid_deleted(settings, user=owner, profile_name=name)


async def process_unpaid_profiles(settings: Settings) -> dict[str, int]:
    stats = {"reminded_3": 0, "reminded_14": 0, "reminded_27": 0, "deleted": 0}
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        result = await session.execute(
            select(Profile)
            .where(Profile.status == ProfileStatus.AWAITING_PAYMENT.value)
            .options(selectinload(Profile.user), selectinload(Profile.photos))
            .limit(80)
        )
        profiles = list(result.scalars().all())
        for profile in profiles:
            start = _anchor(profile)
            if start is None:
                continue
            age = now - start
            user = profile.user
            if user is None:
                continue
            if age >= timedelta(days=DELETE_AFTER_DAYS):
                await delete_unpaid_profile(session, settings, profile=profile)
                stats["deleted"] += 1
                continue
            for days, field, key in (
                (27, "unpaid_reminded_27d_at", "reminded_27"),
                (14, "unpaid_reminded_14d_at", "reminded_14"),
                (3, "unpaid_reminded_3d_at", "reminded_3"),
            ):
                if age < timedelta(days=days):
                    continue
                if getattr(profile, field) is not None:
                    continue
                ok = await notify_unpaid_reminder(
                    settings, user=user, profile=profile, day=days
                )
                if ok:
                    setattr(profile, field, now)
                    session.add(profile)
                    stats[key] += 1
                break
        await session.commit()
    return stats
