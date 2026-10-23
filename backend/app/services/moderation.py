"""Admin moderation actions for profiles."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
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
from app.services.slots import place_profile_at

REJECT_PRESETS = [
    {
        "id": "photos",
        "text": "Пожалуйста, загрузите другие фото: лицо крупным планом, без сильных фильтров, три разных снимка.",
    },
    {
        "id": "blurry",
        "text": "Фото слишком тёмные или размытые. Нужны чёткие фото, где вас хорошо видно.",
    },
    {
        "id": "about",
        "text": "Расскажите о себе подробнее: кто вы, чем живёте, кого ищете. Сейчас текста мало для публикации.",
    },
    {
        "id": "age",
        "text": "Возраст или данные в анкете выглядят недостоверно. Проверьте поля и отправьте снова.",
    },
    {
        "id": "rules",
        "text": "Анкета не соответствует правилам. Уберите контакты, рекламу и ссылки — и отправьте снова.",
    },
]


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


def _profile_status_filter(
    *,
    status: str | None = None,
    statuses: list[str] | None = None,
):
    if status:
        return Profile.status == status
    if statuses:
        return Profile.status.in_(statuses)
    return None


def _apply_profile_filters(
    stmt,
    *,
    status: str | None = None,
    statuses: list[str] | None = None,
    gender: str | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    has_username: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    filt = _profile_status_filter(status=status, statuses=statuses)
    if filt is not None:
        stmt = stmt.where(filt)
    if gender in {"male", "female"}:
        stmt = stmt.where(Profile.gender == gender)
    if age_min is not None:
        stmt = stmt.where(Profile.age >= age_min)
    if age_max is not None:
        stmt = stmt.where(Profile.age <= age_max)
    if date_from is not None:
        stmt = stmt.where(Profile.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Profile.created_at <= date_to)
    if has_username is True:
        stmt = stmt.where(
            or_(
                and_(Profile.telegram_username.is_not(None), Profile.telegram_username != ""),
                and_(User.telegram_username.is_not(None), User.telegram_username != ""),
            )
        )
    elif has_username is False:
        stmt = stmt.where(
            or_(Profile.telegram_username.is_(None), Profile.telegram_username == ""),
            or_(User.telegram_username.is_(None), User.telegram_username == ""),
        )
    return stmt


async def count_profiles(
    session: AsyncSession,
    *,
    status: str | None = None,
    statuses: list[str] | None = None,
    gender: str | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    has_username: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    stmt = select(func.count()).select_from(Profile).join(User, Profile.user_id == User.id)
    stmt = _apply_profile_filters(
        stmt,
        status=status,
        statuses=statuses,
        gender=gender,
        age_min=age_min,
        age_max=age_max,
        has_username=has_username,
        date_from=date_from,
        date_to=date_to,
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def list_profiles(
    session: AsyncSession,
    *,
    status: str | None = None,
    statuses: list[str] | None = None,
    gender: str | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    has_username: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Profile]:
    """Lean list: profile + user only (no photos collection)."""
    stmt = (
        select(Profile)
        .join(User, Profile.user_id == User.id)
        .options(selectinload(Profile.user))
        .order_by(Profile.updated_at.desc(), Profile.id.desc())
        .limit(limit)
        .offset(offset)
    )
    stmt = _apply_profile_filters(
        stmt,
        status=status,
        statuses=statuses,
        gender=gender,
        age_min=age_min,
        age_max=age_max,
        has_username=has_username,
        date_from=date_from,
        date_to=date_to,
    )
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

    from app.services.entitlements import active_subscription, apply_top_until, has_unlimited
    from app.services.notify import notify_unlimited_queued
    from app.services.payments import queue_profile_after_entitlement

    if await has_unlimited(session, user.id):
        sub = await active_subscription(session, user.id)
        if sub is not None:
            apply_top_until(profile, sub.expires_at)
            session.add(profile)
            await session.commit()
        await queue_profile_after_entitlement(session, settings, profile=profile, user=user)
        await notify_unlimited_queued(settings, user=user, profile=profile)
        return await get_profile_admin(session, profile.id)  # type: ignore[return-value]

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
    await place_profile_at(session, settings, profile, scheduled_at)
    session.add(profile)
    await session.commit()

    user = profile.user
    if user is None:
        result = await session.execute(select(User).where(User.id == profile.user_id))
        user = result.scalar_one()
    await notify_user_scheduled(settings, user=user, profile=profile, scheduled_at=scheduled_at)
    return await get_profile_admin(session, profile.id)  # type: ignore[return-value]


def _user_search_filters(query: str):
    q = query.strip()
    if not q:
        return None
    filters = [
        User.telegram_username.ilike(f"%{q.lstrip('@')}%"),
        User.telegram_first_name.ilike(f"%{q}%"),
        User.stated_name.ilike(f"%{q}%"),
    ]
    if q.isdigit():
        filters.append(User.telegram_id == int(q))
        filters.append(User.id == int(q))
    return or_(*filters)


async def count_users(session: AsyncSession, *, query: str = "") -> int:
    stmt = select(func.count()).select_from(User)
    filt = _user_search_filters(query)
    if filt is not None:
        stmt = stmt.where(filt)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def search_users(
    session: AsyncSession,
    *,
    query: str,
    limit: int = 40,
    offset: int = 0,
) -> list[User]:
    stmt = (
        select(User)
        .options(selectinload(User.profile))
        .order_by(User.id.desc())
        .limit(limit)
        .offset(offset)
    )
    filt = _user_search_filters(query)
    if filt is not None:
        stmt = stmt.where(filt)
    result = await session.execute(stmt)
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


def period_bounds(period: str | None, tz: ZoneInfo) -> tuple[datetime | None, datetime]:
    now = datetime.now(tz)
    end = now.astimezone(timezone.utc)
    if not period or period == "lifetime":
        return None, end
    start_local = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start_local = start_local - timedelta(days=start_local.weekday())
    elif period == "month":
        start_local = start_local.replace(day=1)
    elif period != "today":
        return None, end
    return start_local.astimezone(timezone.utc), end


async def list_credit_ledger(
    session: AsyncSession,
    user_id: int,
    *,
    limit: int = 50,
) -> list[CreditLedgerEntry]:
    result = await session.execute(
        select(CreditLedgerEntry)
        .where(CreditLedgerEntry.user_id == user_id)
        .order_by(CreditLedgerEntry.created_at.desc(), CreditLedgerEntry.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def admin_stats(session: AsyncSession, *, period: str | None = None, tz_name: str = "Europe/Rome") -> dict:
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
                            PaymentProduct.MESSAGE_PACK_10.value,
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

    start, end = period_bounds(period, ZoneInfo(tz_name))

    def _window(column):
        conds = [column.is_not(None), column <= end]
        if start is not None:
            conds.append(column >= start)
        return and_(*conds)

    async def _count(stmt) -> int:
        return int((await session.execute(stmt)).scalar_one())

    funnel_submitted = await _count(
        select(func.count())
        .select_from(Profile)
        .where(Profile.status != ProfileStatus.DRAFT.value, _window(Profile.created_at))
    )
    funnel_approved = await _count(
        select(func.count()).select_from(Profile).where(_window(Profile.approved_at))
    )
    funnel_paid = await _count(
        select(func.count()).select_from(Profile).where(_window(Profile.paid_at))
    )
    funnel_published = await _count(
        select(func.count()).select_from(Profile).where(_window(Profile.published_at))
    )
    letters_new = await _count(
        select(func.count()).select_from(MessageRequest).where(_window(MessageRequest.created_at))
    )
    letters_replied_period = await _count(
        select(func.count()).select_from(MessageRequest).where(_window(MessageRequest.responded_at))
    )
    letters_unlocked_period = await _count(
        select(func.count()).select_from(MessageRequest).where(_window(MessageRequest.unlocked_at))
    )
    stars_period = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.stars_amount), 0)).where(
                Payment.status == PaymentStatus.COMPLETED.value,
                Payment.currency == "XTR",
                _window(Payment.completed_at),
            )
        )
    ).scalar_one()

    return {
        "period": period or "lifetime",
        "users_total": users_total,
        "users_blocked": blocked,
        "users_soft_banned": soft_banned,
        "profiles_new": await count_profiles(ProfileStatus.NEW.value),
        "profiles_awaiting_payment": await count_profiles(ProfileStatus.AWAITING_PAYMENT.value),
        "profiles_queued": await count_profiles(ProfileStatus.QUEUED.value),
        "profiles_published": await count_profiles(ProfileStatus.PUBLISHED.value),
        "profiles_rejected": await count_profiles(ProfileStatus.REJECTED.value),
        "payments_completed": payments_done,
        "stars_earned": int(stars_period if period and period != "lifetime" else stars_sum),
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
        "funnel_submitted": funnel_submitted,
        "funnel_approved": funnel_approved,
        "funnel_paid": funnel_paid,
        "funnel_queued": funnel_paid,
        "funnel_published": funnel_published,
        "letters_new": letters_new,
        "letters_replied_period": letters_replied_period,
        "letters_unlocked_period": letters_unlocked_period,
    }
