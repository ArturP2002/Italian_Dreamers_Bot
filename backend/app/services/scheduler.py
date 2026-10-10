"""Background loop: publish queued profiles + ad slot FIFO / TTL / reminders (Rome time)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.database import async_session_factory
from app.models import Profile, ProfileStatus
from app.services.ads import process_ad_queue
from app.services.channel import publish_profile_to_channel
from app.services.notify import notify_user_published
from app.services.telegram_api import get_bot_username

logger = logging.getLogger(__name__)


async def publish_due_profiles(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    published = 0
    async with async_session_factory() as session:
        result = await session.execute(
            select(Profile)
            .where(
                Profile.status == ProfileStatus.QUEUED.value,
                Profile.scheduled_at.is_not(None),
                Profile.scheduled_at <= now,
            )
            .options(selectinload(Profile.user), selectinload(Profile.photos))
            .order_by(Profile.scheduled_at.asc())
            .limit(5)
        )
        profiles = list(result.scalars().all())
        if not profiles:
            return 0
        username = await get_bot_username(settings)
        for profile in profiles:
            try:
                await publish_profile_to_channel(
                    session, settings, profile.id, bot_username=username
                )
                user = profile.user
                if user is not None:
                    await notify_user_published(settings, user=user, profile=profile)
                published += 1
            except Exception:
                logger.exception("Failed to publish profile %s", profile.id)
    return published


async def scheduler_loop(stop_event: asyncio.Event, interval_seconds: float = 60.0) -> None:
    settings = get_settings()
    logger.info("Publication scheduler started (every %ss)", interval_seconds)
    while not stop_event.is_set():
        try:
            n = await publish_due_profiles(settings)
            if n:
                logger.info("Published %s due profile(s)", n)
        except Exception:
            logger.exception("Scheduler tick failed (profiles)")
        try:
            ad_stats = await process_ad_queue(settings)
            if any(ad_stats.values()):
                logger.info("Ad queue tick: %s", ad_stats)
        except Exception:
            logger.exception("Scheduler tick failed (ads)")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue
