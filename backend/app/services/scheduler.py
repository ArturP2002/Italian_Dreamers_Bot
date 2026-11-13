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
from app.services.slots import backfill_unscheduled_queued
from app.services.unpaid import process_unpaid_profiles
from app.services.username_nudge import process_username_nudges

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
            unpaid_stats = await process_unpaid_profiles(settings)
            if any(unpaid_stats.values()):
                logger.info("Unpaid tick: %s", unpaid_stats)
        except Exception:
            logger.exception("Scheduler tick failed (unpaid)")
        try:
            async with async_session_factory() as session:
                filled = await backfill_unscheduled_queued(session, settings)
                if filled:
                    await session.commit()
                    logger.info("Assigned publication slots: %s", filled)
        except Exception:
            logger.exception("Scheduler tick failed (slots)")
        try:
            nudged = await process_username_nudges(settings)
            if nudged:
                logger.info("Username nudges sent: %s", nudged)
        except Exception:
            logger.exception("Scheduler tick failed (username nudges)")
        try:
            from app.services.weekly_report import maybe_send_weekly_report

            report = await maybe_send_weekly_report(settings)
            if report is not None:
                logger.info("Weekly report sent id=%s", report.id)
        except Exception:
            logger.exception("Scheduler tick failed (weekly report)")
        try:
            from app.services.messages import expire_due_letters

            async with async_session_factory() as session:
                expired = await expire_due_letters(session, settings)
            if expired:
                logger.info("Expired unanswered letters: %s", expired)
        except Exception:
            logger.exception("Scheduler tick failed (letter timeout)")
        try:
            from app.services.subscription_jobs import (
                notify_credits_cut_once,
                process_subscription_renewal_reminders,
            )

            reminded = await process_subscription_renewal_reminders(settings)
            if reminded:
                logger.info("Subscription renewal reminders: %s", reminded)
            cut = await notify_credits_cut_once(settings)
            if cut:
                logger.info("Credits-cut notices: %s", cut)
        except Exception:
            logger.exception("Scheduler tick failed (subscription jobs)")
        try:
            # Once per Rome day around 18:00 — cheap throttle via module flag.
            from datetime import datetime
            from zoneinfo import ZoneInfo

            from app.services.newcomers import publish_daily_newcomers

            rome = ZoneInfo("Europe/Rome")
            now_rome = datetime.now(rome)
            stamp = getattr(scheduler_loop, "_newcomers_day", None)
            if now_rome.hour >= 18 and stamp != now_rome.date().isoformat():
                async with async_session_factory() as session:
                    stats = await publish_daily_newcomers(session, settings)
                scheduler_loop._newcomers_day = now_rome.date().isoformat()  # type: ignore[attr-defined]
                if stats.get("batches"):
                    logger.info("Newcomers collage: %s", stats)
        except Exception:
            logger.exception("Scheduler tick failed (newcomers)")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue
