"""Ad requests: submit, moderate, pay, FIFO 10:00 Rome-time slot, 48h TTL, reminders."""

from __future__ import annotations

import html
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import AdRequest, AdRequestStatus, User
from app.services.notify import (
    notify_admins_ad_submitted,
    notify_user_ad_activated,
    notify_user_ad_approved,
    notify_user_ad_expired,
    notify_user_ad_rejected,
    notify_user_ad_reminder,
)
from app.services.payments import create_ad_payment, send_ad_invoice
from app.services.telegram_api import delete_message, send_message, send_photo_media

logger = logging.getLogger(__name__)

AD_TTL_HOURS = 48
AD_SLOT_HOUR = 10  # APP_TIMEZONE (Europe/Rome)
AD_CATEGORIES = frozenset({"restaurants", "mens_goods", "language_courses", "other"})


class AdServiceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def app_tz(settings: Settings) -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


def _normalize_category(raw: str | None) -> str:
    value = (raw or "other").strip().lower()
    if value in AD_CATEGORIES:
        return value
    return "other"


async def get_ad(session: AsyncSession, ad_id: int) -> AdRequest | None:
    result = await session.execute(
        select(AdRequest).where(AdRequest.id == ad_id).options(selectinload(AdRequest.user))
    )
    return result.scalar_one_or_none()


async def list_ads(
    session: AsyncSession,
    *,
    status: str | None = None,
    statuses: list[str] | None = None,
    user_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdRequest]:
    stmt = (
        select(AdRequest)
        .options(selectinload(AdRequest.user))
        .order_by(AdRequest.created_at.desc(), AdRequest.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if user_id is not None:
        stmt = stmt.where(AdRequest.user_id == user_id)
    if status:
        stmt = stmt.where(AdRequest.status == status)
    elif statuses:
        stmt = stmt.where(AdRequest.status.in_(statuses))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_ad_request(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    title: str,
    category: str,
    body: str,
    contact: str | None,
    desired_date: str | None,
    media_file_id: str | None = None,
) -> AdRequest:
    if user.is_blocked:
        raise AdServiceError("blocked", "User is blocked")
    cleaned_title = (title or "").strip()
    cleaned_body = (body or "").strip()
    cleaned_contact = (contact or "").strip() or None
    cleaned_desired = (desired_date or "").strip() or None
    if len(cleaned_title) < 2 or len(cleaned_title) > 120:
        raise AdServiceError("title_invalid", "Title must be 2–120 characters")
    if len(cleaned_body) < 10 or len(cleaned_body) > 2000:
        raise AdServiceError("body_invalid", "Body must be 10–2000 characters")
    if cleaned_contact and len(cleaned_contact) > 255:
        raise AdServiceError("contact_invalid", "Contact too long")

    ad = AdRequest(
        user_id=user.id,
        status=AdRequestStatus.PENDING.value,
        title=cleaned_title,
        category=_normalize_category(category),
        body=cleaned_body,
        contact=cleaned_contact,
        desired_date=cleaned_desired,
        media_file_id=media_file_id,
    )
    session.add(ad)
    await session.commit()
    await session.refresh(ad)
    await notify_admins_ad_submitted(settings, user=user, ad=ad)
    return await get_ad(session, ad.id)  # type: ignore[return-value]


async def update_ad_request(
    session: AsyncSession,
    ad: AdRequest,
    *,
    title: str | None = None,
    category: str | None = None,
    body: str | None = None,
    contact: str | None = None,
    desired_date: str | None = None,
    media_file_id: str | None = None,
) -> AdRequest:
    if ad.status not in {
        AdRequestStatus.PENDING.value,
        AdRequestStatus.REJECTED.value,
        AdRequestStatus.AWAITING_PAYMENT.value,
        AdRequestStatus.QUEUED.value,
    }:
        raise AdServiceError("bad_status", f"Cannot edit ad in status {ad.status}")

    if title is not None:
        cleaned = title.strip()
        if len(cleaned) < 2 or len(cleaned) > 120:
            raise AdServiceError("title_invalid", "Title must be 2–120 characters")
        ad.title = cleaned
    if category is not None:
        ad.category = _normalize_category(category)
    if body is not None:
        cleaned = body.strip()
        if len(cleaned) < 10 or len(cleaned) > 2000:
            raise AdServiceError("body_invalid", "Body must be 10–2000 characters")
        ad.body = cleaned
    if contact is not None:
        ad.contact = contact.strip() or None
    if desired_date is not None:
        ad.desired_date = desired_date.strip() or None
    if media_file_id is not None:
        ad.media_file_id = media_file_id or None

    session.add(ad)
    await session.commit()
    return await get_ad(session, ad.id)  # type: ignore[return-value]


async def approve_ad(
    session: AsyncSession,
    settings: Settings,
    ad: AdRequest,
) -> AdRequest:
    if ad.status not in {AdRequestStatus.PENDING.value, AdRequestStatus.REJECTED.value}:
        raise ValueError(f"Cannot approve ad in status {ad.status}")

    ad.status = AdRequestStatus.AWAITING_PAYMENT.value
    ad.moderation_feedback = None
    session.add(ad)
    await session.commit()

    user = ad.user
    if user is None:
        result = await session.execute(select(User).where(User.id == ad.user_id))
        user = result.scalar_one()

    payment = await create_ad_payment(session, settings, user=user, ad=ad)
    await notify_user_ad_approved(settings, user=user, ad=ad, stars=payment.stars_amount)
    await send_ad_invoice(settings, user=user, ad=ad, payment=payment)
    return await get_ad(session, ad.id)  # type: ignore[return-value]


async def reject_ad(
    session: AsyncSession,
    settings: Settings,
    ad: AdRequest,
    feedback: str,
) -> AdRequest:
    if ad.status not in {
        AdRequestStatus.PENDING.value,
        AdRequestStatus.AWAITING_PAYMENT.value,
    }:
        raise ValueError(f"Cannot reject ad in status {ad.status}")

    ad.status = AdRequestStatus.REJECTED.value
    ad.moderation_feedback = feedback.strip()
    session.add(ad)
    await session.commit()

    user = ad.user
    if user is None:
        result = await session.execute(select(User).where(User.id == ad.user_id))
        user = result.scalar_one()
    await notify_user_ad_rejected(settings, user=user, ad=ad, feedback=feedback)
    return await get_ad(session, ad.id)  # type: ignore[return-value]


def next_10am_after(dt: datetime, tz: ZoneInfo) -> datetime:
    local = dt.astimezone(tz)
    candidate = local.replace(hour=AD_SLOT_HOUR, minute=0, second=0, microsecond=0)
    if local >= candidate:
        candidate = candidate + timedelta(days=1)
    return candidate.astimezone(timezone.utc)


async def compute_next_ad_slot(session: AsyncSession, settings: Settings) -> datetime:
    """FIFO: next free 10:00 (Rome time) after the last active/queued slot chain."""
    tz = app_tz(settings)
    now = datetime.now(timezone.utc)

    active = await session.execute(
        select(AdRequest)
        .where(AdRequest.status == AdRequestStatus.ACTIVE.value)
        .order_by(AdRequest.expires_at.desc())
        .limit(1)
    )
    active_ad = active.scalar_one_or_none()

    queued = await session.execute(
        select(AdRequest)
        .where(
            AdRequest.status == AdRequestStatus.QUEUED.value,
            AdRequest.scheduled_at.is_not(None),
        )
        .order_by(AdRequest.scheduled_at.desc())
        .limit(1)
    )
    queued_ad = queued.scalar_one_or_none()

    anchor = now
    if active_ad and active_ad.expires_at:
        anchor = max(anchor, active_ad.expires_at)
    if queued_ad and queued_ad.scheduled_at:
        # queued slot occupies 48h from its scheduled start
        queued_end = queued_ad.scheduled_at + timedelta(hours=AD_TTL_HOURS)
        anchor = max(anchor, queued_end)

    return next_10am_after(anchor, tz)


def format_ad_caption(ad: AdRequest) -> str:
    category_labels = {
        "restaurants": "🍽 Ristoranti / Рестораны",
        "mens_goods": "🛍 Per lui / Товары для мужчин",
        "language_courses": "📚 Corsi / Языковые курсы",
        "other": "✨ Partner / Партнёр",
    }
    cat = category_labels.get(ad.category, category_labels["other"])
    title = html.escape(ad.title)
    body = html.escape(ad.body)
    lines = [f"<b>{title}</b>", cat, "", body]
    if ad.contact:
        lines.extend(["", f"✉️ {html.escape(ad.contact)}"])
    return "\n".join(lines)


async def activate_ad(
    session: AsyncSession,
    settings: Settings,
    ad: AdRequest,
    *,
    now: datetime | None = None,
) -> AdRequest:
    now = now or datetime.now(timezone.utc)
    if ad.status != AdRequestStatus.QUEUED.value:
        raise AdServiceError("bad_status", "Only queued ads can be activated")
    if settings.channel_id:
        caption = format_ad_caption(ad)
        try:
            if ad.media_file_id:
                result = await send_photo_media(
                    settings, settings.channel_id, ad.media_file_id, caption=caption
                )
            else:
                result = await send_message(
                    settings, settings.channel_id, caption, parse_mode="HTML"
                )
            msg = result.get("result") or {}
            ad.channel_message_id = msg.get("message_id")
        except Exception:
            logger.exception("Failed to post ad %s to channel", ad.id)
            raise

    ad.status = AdRequestStatus.ACTIVE.value
    ad.activated_at = now
    ad.expires_at = now + timedelta(hours=AD_TTL_HOURS)
    session.add(ad)
    await session.commit()

    user = ad.user
    if user is None:
        result = await session.execute(select(User).where(User.id == ad.user_id))
        user = result.scalar_one()
    await notify_user_ad_activated(settings, user=user, ad=ad)
    return await get_ad(session, ad.id)  # type: ignore[return-value]


async def expire_ad(
    session: AsyncSession,
    settings: Settings,
    ad: AdRequest,
) -> AdRequest:
    if ad.status != AdRequestStatus.ACTIVE.value:
        return ad

    if ad.channel_message_id and settings.channel_id:
        try:
            await delete_message(settings, settings.channel_id, int(ad.channel_message_id))
        except Exception:
            logger.exception("Failed to delete ad message %s", ad.channel_message_id)

    ad.status = AdRequestStatus.EXPIRED.value
    session.add(ad)
    await session.commit()

    user = ad.user
    if user is None:
        result = await session.execute(select(User).where(User.id == ad.user_id))
        user = result.scalar_one()
    await notify_user_ad_expired(settings, user=user, ad=ad)
    return await get_ad(session, ad.id)  # type: ignore[return-value]


async def expire_due_ads(session: AsyncSession, settings: Settings) -> int:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(AdRequest)
        .where(
            AdRequest.status == AdRequestStatus.ACTIVE.value,
            AdRequest.expires_at.is_not(None),
            AdRequest.expires_at <= now,
        )
        .options(selectinload(AdRequest.user))
        .order_by(AdRequest.expires_at.asc())
        .limit(10)
    )
    ads = list(result.scalars().all())
    for ad in ads:
        await expire_ad(session, settings, ad)
    return len(ads)


async def activate_due_ads(session: AsyncSession, settings: Settings) -> int:
    """Activate next queued ad when slot is free and scheduled_at is due (10:00 Rome time FIFO)."""
    now = datetime.now(timezone.utc)
    active_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(AdRequest)
                .where(AdRequest.status == AdRequestStatus.ACTIVE.value)
            )
        ).scalar_one()
    )
    if active_count > 0:
        return 0

    result = await session.execute(
        select(AdRequest)
        .where(
            AdRequest.status == AdRequestStatus.QUEUED.value,
            AdRequest.paid_at.is_not(None),
            AdRequest.scheduled_at.is_not(None),
            AdRequest.scheduled_at <= now,
        )
        .options(selectinload(AdRequest.user))
        .order_by(AdRequest.scheduled_at.asc(), AdRequest.id.asc())
        .limit(1)
    )
    ad = result.scalar_one_or_none()
    if ad is None:
        return 0
    await activate_ad(session, settings, ad, now=now)
    return 1


async def send_due_ad_reminders(session: AsyncSession, settings: Settings) -> int:
    now = datetime.now(timezone.utc)
    sent = 0

    # +7 days after expiry (expires_at)
    result_7 = await session.execute(
        select(AdRequest)
        .where(
            AdRequest.status == AdRequestStatus.EXPIRED.value,
            AdRequest.expires_at.is_not(None),
            AdRequest.expires_at <= now - timedelta(days=7),
            AdRequest.reminded_7d_at.is_(None),
        )
        .options(selectinload(AdRequest.user))
        .limit(20)
    )
    for ad in result_7.scalars().all():
        user = ad.user
        if user is None:
            continue
        await notify_user_ad_reminder(settings, user=user, ad=ad, kind="7d")
        ad.reminded_7d_at = now
        session.add(ad)
        sent += 1

    result_30 = await session.execute(
        select(AdRequest)
        .where(
            AdRequest.status == AdRequestStatus.EXPIRED.value,
            AdRequest.expires_at.is_not(None),
            AdRequest.expires_at <= now - timedelta(days=30),
            AdRequest.reminded_30d_at.is_(None),
        )
        .options(selectinload(AdRequest.user))
        .limit(20)
    )
    for ad in result_30.scalars().all():
        user = ad.user
        if user is None:
            continue
        await notify_user_ad_reminder(settings, user=user, ad=ad, kind="30d")
        ad.reminded_30d_at = now
        session.add(ad)
        sent += 1

    if sent:
        await session.commit()
    return sent


async def process_ad_queue(settings: Settings) -> dict[str, int]:
    from app.database import async_session_factory

    async with async_session_factory() as session:
        expired = await expire_due_ads(session, settings)
        activated = await activate_due_ads(session, settings)
        reminded = await send_due_ad_reminders(session, settings)
    return {"expired": expired, "activated": activated, "reminded": reminded}
