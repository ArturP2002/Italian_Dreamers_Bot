"""Admin moderation actions for profiles."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import (
    AdRequest,
    AdRequestStatus,
    Complaint,
    ComplaintStatus,
    CreditLedgerEntry,
    LedgerEntryType,
    MessageRequest,
    MessageRequestStatus,
    Payment,
    PaymentProduct,
    PaymentStatus,
    Profile,
    ProfilePhoto,
    ProfileStatus,
    User,
)
from app.services.payments import create_publish_payment, send_publish_invoice
from app.services.notify import (
    notify_user_profile_approved,
    notify_user_profile_rejected,
    notify_user_scheduled,
)


def app_tz(settings: Settings) -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


async def get_profile_admin(session: AsyncSession, profile_id: int) -> Profile | None:
    result = await session.execute(
        select(Profile)
        .where(Profile.id == profile_id)
        .options(selectinload(Profile.photos), selectinload(Profile.user))
    )
    return result.scalar_one_or_none()


async def first_photo_file_ids(
    session: AsyncSession,
    profile_ids: list[int],
) -> dict[int, str]:
    """One query: first photo file_id per profile (by position). No full photo graphs."""
    if not profile_ids:
        return {}
    result = await session.execute(
        select(ProfilePhoto)
        .where(ProfilePhoto.profile_id.in_(profile_ids))
        .order_by(ProfilePhoto.profile_id.asc(), ProfilePhoto.position.asc())
    )
    out: dict[int, str] = {}
    for photo in result.scalars().all():
        if photo.profile_id not in out:
            out[photo.profile_id] = photo.file_id
    return out


async def list_profiles(
    session: AsyncSession,
    *,
    status: str | None = None,
    statuses: list[str] | None = None,
    limit: int = 25,
    offset: int = 0,
) -> list[Profile]:
    """Lean list: profile + user only (no photos collection)."""
    stmt = (
        select(Profile)
        .options(selectinload(Profile.user))
        .order_by(Profile.updated_at.desc(), Profile.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        stmt = stmt.where(Profile.status == status)
    elif statuses:
        stmt = stmt.where(Profile.status.in_(statuses))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def approve_profile(
    session: AsyncSession,
    settings: Settings,
    profile: Profile,
) -> Profile:
    if profile.status not in {ProfileStatus.NEW.value, ProfileStatus.REJECTED.value}:
        raise ValueError(f"Cannot approve profile in status {profile.status}")

    profile.status = ProfileStatus.AWAITING_PAYMENT.value
    profile.approved_at = datetime.now(timezone.utc)
    profile.moderation_feedback = None
    session.add(profile)
    await session.commit()

    user = profile.user
    if user is None:
        result = await session.execute(select(User).where(User.id == profile.user_id))
        user = result.scalar_one()

    payment = await create_publish_payment(session, settings, user=user, profile=profile)
    await notify_user_profile_approved(settings, user=user, profile=profile, stars=payment.stars_amount)
    await send_publish_invoice(settings, user=user, profile=profile, payment=payment)

    return await get_profile_admin(session, profile.id)  # type: ignore[return-value]


async def reject_profile(
    session: AsyncSession,
    settings: Settings,
    profile: Profile,
    feedback: str,
) -> Profile:
    if profile.status not in {ProfileStatus.NEW.value, ProfileStatus.AWAITING_PAYMENT.value}:
        raise ValueError(f"Cannot reject profile in status {profile.status}")

    profile.status = ProfileStatus.REJECTED.value
    profile.moderation_feedback = feedback.strip()
    profile.approved_at = None
    session.add(profile)
    await session.commit()

    user = profile.user
    if user is None:
        result = await session.execute(select(User).where(User.id == profile.user_id))
        user = result.scalar_one()
    await notify_user_profile_rejected(settings, user=user, profile=profile, feedback=feedback)
    return await get_profile_admin(session, profile.id)  # type: ignore[return-value]


async def schedule_profile(
    session: AsyncSession,
    settings: Settings,
    profile: Profile,
    scheduled_at: datetime,
) -> Profile:
    if profile.status != ProfileStatus.QUEUED.value:
        raise ValueError("Only paid (queued) profiles can be scheduled")
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=app_tz(settings))
    profile.scheduled_at = scheduled_at.astimezone(timezone.utc)
    session.add(profile)
    await session.commit()

    user = profile.user
    if user is None:
        result = await session.execute(select(User).where(User.id == profile.user_id))
        user = result.scalar_one()
    await notify_user_scheduled(settings, user=user, profile=profile, scheduled_at=scheduled_at)
    return await get_profile_admin(session, profile.id)  # type: ignore[return-value]


async def search_users(
    session: AsyncSession,
    *,
    query: str,
    limit: int = 40,
) -> list[User]:
    q = query.strip()
    if not q:
        result = await session.execute(
            select(User)
            .options(selectinload(User.profile))
            .order_by(User.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    filters = [
        User.telegram_username.ilike(f"%{q.lstrip('@')}%"),
        User.telegram_first_name.ilike(f"%{q}%"),
        User.stated_name.ilike(f"%{q}%"),
    ]
    if q.isdigit():
        filters.append(User.telegram_id == int(q))
        filters.append(User.id == int(q))

    result = await session.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(or_(*filters))
        .order_by(User.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def set_user_blocked(session: AsyncSession, user: User, blocked: bool) -> User:
    user.is_blocked = blocked
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def grant_credits(
    session: AsyncSession,
    user: User,
    delta: int,
    *,
    note: str | None = None,
) -> User:
    if delta == 0:
        return user
    user.message_credits = max(0, user.message_credits + delta)
    session.add(user)
    session.add(
        CreditLedgerEntry(
            user_id=user.id,
            entry_type=LedgerEntryType.ADMIN_GRANT.value,
            delta=delta,
            balance_after=user.message_credits,
            note=note or "admin_grant",
        )
    )
    await session.commit()
    await session.refresh(user)
    return user


async def admin_stats(session: AsyncSession) -> dict:
    async def count_profiles(status: str) -> int:
        result = await session.execute(
            select(func.count()).select_from(Profile).where(Profile.status == status)
        )
        return int(result.scalar_one())

    async def count_ads(status: str) -> int:
        result = await session.execute(
            select(func.count()).select_from(AdRequest).where(AdRequest.status == status)
        )
        return int(result.scalar_one())

    users_total = int(
        (await session.execute(select(func.count()).select_from(User))).scalar_one()
    )
    blocked = int(
        (
            await session.execute(
                select(func.count()).select_from(User).where(User.is_blocked.is_(True))
            )
        ).scalar_one()
    )
    soft_banned = int(
        (
            await session.execute(
                select(func.count())
                .select_from(User)
                .where(User.soft_ban_until.is_not(None), User.soft_ban_until > func.now())
            )
        ).scalar_one()
    )
    payments_done = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Payment)
                .where(Payment.status == PaymentStatus.COMPLETED.value)
            )
        ).scalar_one()
    )
    stars_sum = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.stars_amount), 0)).where(
                Payment.status == PaymentStatus.COMPLETED.value
            )
        )
    ).scalar_one()
    publish_payments = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Payment)
                .where(
                    Payment.product == PaymentProduct.PROFILE_PUBLISH.value,
                    Payment.status == PaymentStatus.COMPLETED.value,
                )
            )
        ).scalar_one()
    )
    credit_payments = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Payment)
                .where(
                    Payment.product.in_(
                        [
                            PaymentProduct.MESSAGE_CREDIT.value,
                            PaymentProduct.MESSAGE_PACK_9.value,
                        ]
                    ),
                    Payment.status == PaymentStatus.COMPLETED.value,
                )
            )
        ).scalar_one()
    )
    ad_payments = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Payment)
                .where(
                    Payment.product == PaymentProduct.AD_SLOT.value,
                    Payment.status == PaymentStatus.COMPLETED.value,
                )
            )
        ).scalar_one()
    )
    credits_granted = (
        await session.execute(
            select(func.coalesce(func.sum(CreditLedgerEntry.delta), 0)).where(
                CreditLedgerEntry.entry_type == LedgerEntryType.ADMIN_GRANT.value
            )
        )
    ).scalar_one()
    letters_pending = int(
        (
            await session.execute(
                select(func.count())
                .select_from(MessageRequest)
                .where(MessageRequest.status == MessageRequestStatus.PENDING.value)
            )
        ).scalar_one()
    )
    letters_rejected = int(
        (
            await session.execute(
                select(func.count())
                .select_from(MessageRequest)
                .where(MessageRequest.status == MessageRequestStatus.REJECTED.value)
            )
        ).scalar_one()
    )
    letters_unlocked = int(
        (
            await session.execute(
                select(func.count())
                .select_from(MessageRequest)
                .where(
                    MessageRequest.status.in_(
                        [
                            MessageRequestStatus.UNLOCKED.value,
                            MessageRequestStatus.CHATTING.value,
                        ]
                    )
                )
            )
        ).scalar_one()
    )
    complaints_open = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Complaint)
                .where(Complaint.status == ComplaintStatus.OPEN.value)
            )
        ).scalar_one()
    )

    return {
        "users_total": users_total,
        "users_blocked": blocked,
        "users_soft_banned": soft_banned,
        "profiles_new": await count_profiles(ProfileStatus.NEW.value),
        "profiles_awaiting_payment": await count_profiles(ProfileStatus.AWAITING_PAYMENT.value),
        "profiles_queued": await count_profiles(ProfileStatus.QUEUED.value),
        "profiles_published": await count_profiles(ProfileStatus.PUBLISHED.value),
        "profiles_rejected": await count_profiles(ProfileStatus.REJECTED.value),
        "payments_completed": payments_done,
        "stars_earned": int(stars_sum),
        "publish_payments": publish_payments,
        "credit_payments": credit_payments,
        "ad_payments": ad_payments,
        "credits_granted": int(credits_granted),
        "letters_pending": letters_pending,
        "letters_rejected": letters_rejected,
        "letters_unlocked": letters_unlocked,
        "complaints_open": complaints_open,
        "ads_pending": await count_ads(AdRequestStatus.PENDING.value),
        "ads_queued": await count_ads(AdRequestStatus.QUEUED.value),
        "ads_active": await count_ads(AdRequestStatus.ACTIVE.value),
        "ads_expired": await count_ads(AdRequestStatus.EXPIRED.value),
    }
