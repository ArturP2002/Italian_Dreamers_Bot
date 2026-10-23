"""Sunday-evening (Rome) weekly AI-ready stats report for admins."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import async_session_factory
from app.models import (
    CommentDecision,
    GroupComment,
    Like,
    Payment,
    PaymentStatus,
    Profile,
    Subscription,
    User,
    WeeklyReport,
)
from app.services.telegram_api import send_message

logger = logging.getLogger(__name__)

REPORT_WEEKDAY = 6  # Sunday
REPORT_HOUR = 19


def report_window(now_local: datetime) -> tuple[datetime, datetime] | None:
    """If it is Sunday after 19:00 Rome, return (Mon 00:00, Sunday 19:00) in UTC."""
    if now_local.weekday() != REPORT_WEEKDAY or now_local.hour < REPORT_HOUR:
        return None
    end_local = now_local.replace(hour=REPORT_HOUR, minute=0, second=0, microsecond=0)
    start_local = (end_local - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


async def build_payload(session: AsyncSession, start: datetime, end: datetime) -> dict:
    async def count(stmt) -> int:
        return int((await session.execute(stmt)).scalar_one() or 0)

    users_new = await count(select(func.count()).select_from(User).where(User.created_at >= start, User.created_at < end))
    profiles_new = await count(
        select(func.count()).select_from(Profile).where(Profile.created_at >= start, Profile.created_at < end)
    )
    published = await count(
        select(func.count()).select_from(Profile).where(
            Profile.published_at.is_not(None),
            Profile.published_at >= start,
            Profile.published_at < end,
        )
    )
    stars = await count(
        select(func.coalesce(func.sum(Payment.stars_amount), 0)).where(
            Payment.status == PaymentStatus.COMPLETED.value,
            Payment.completed_at.is_not(None),
            Payment.completed_at >= start,
            Payment.completed_at < end,
        )
    )
    likes = await count(select(func.count()).select_from(Like).where(Like.created_at >= start, Like.created_at < end))
    matches = await count(
        select(func.count()).select_from(Like).where(
            Like.matched_at.is_not(None),
            Like.matched_at >= start,
            Like.matched_at < end,
        )
    )
    comments_deleted = await count(
        select(func.count()).select_from(GroupComment).where(
            GroupComment.decision == CommentDecision.DELETE.value,
            GroupComment.created_at >= start,
            GroupComment.created_at < end,
        )
    )
    subs = await count(
        select(func.count()).select_from(Subscription).where(
            Subscription.started_at >= start,
            Subscription.started_at < end,
        )
    )
    return {
        "users_new": users_new,
        "profiles_new": profiles_new,
        "published": published,
        "stars_earned": stars,
        "likes": likes,
        "matches": matches,
        "comments_deleted": comments_deleted,
        "subscriptions_started": subs,
    }


def format_report(payload: dict, start: datetime, end: datetime, tz: str) -> str:
    zone = ZoneInfo(tz)
    a = start.astimezone(zone).strftime("%d.%m")
    b = end.astimezone(zone).strftime("%d.%m.%Y")
    return (
        f"📊 Неделя {a}–{b} ({tz})\n\n"
        f"Новых пользователей: {payload.get('users_new', 0)}\n"
        f"Новых анкет: {payload.get('profiles_new', 0)}\n"
        f"Опубликовано в канал: {payload.get('published', 0)}\n"
        f"Звёзд: {payload.get('stars_earned', 0)}\n"
        f"Лайков: {payload.get('likes', 0)}\n"
        f"Мэтчей: {payload.get('matches', 0)}\n"
        f"Удалено комментариев: {payload.get('comments_deleted', 0)}\n"
        f"Новых безлимитов: {payload.get('subscriptions_started', 0)}"
    )


async def maybe_send_weekly_report(settings: Settings) -> WeeklyReport | None:
    zone = ZoneInfo(settings.app_timezone)
    now_local = datetime.now(zone)
    window = report_window(now_local)
    if window is None:
        return None
    start, end = window
    async with async_session_factory() as session:
        existing = await session.execute(select(WeeklyReport).where(WeeklyReport.period_end == end))
        if existing.scalar_one_or_none() is not None:
            return None
        payload = await build_payload(session, start, end)
        row = WeeklyReport(period_start=start, period_end=end, payload=payload, sent_at=datetime.now(timezone.utc))
        session.add(row)
        await session.commit()
        await session.refresh(row)
        text = format_report(payload, start, end, settings.app_timezone)
        for admin_id in settings.admin_ids:
            try:
                await send_message(settings, admin_id, text, parse_mode=None)
            except Exception:
                logger.exception("Failed to send weekly report to %s", admin_id)
        return row


async def list_reports(session: AsyncSession, limit: int = 12) -> list[WeeklyReport]:
    result = await session.execute(select(WeeklyReport).order_by(WeeklyReport.period_end.desc()).limit(limit))
    return list(result.scalars().all())
