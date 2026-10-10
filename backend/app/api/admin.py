"""Admin Mini App API: moderation, queue, users, payments, stats."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import AuthContext, require_admin
from app.config import Settings, get_settings
from app.database import get_session
from app.models import AdRequest, Complaint, Payment, Profile, ProfileStatus, User
from app.services.ads import (
    AdServiceError,
    activate_ad,
    approve_ad,
    get_ad,
    list_ads,
    reject_ad,
    update_ad_request,
)
from app.services.channel import publish_profile_to_channel
from app.services.complaints import get_complaint, list_complaints, resolve_complaint
from app.services.greeting_video import video_url
from app.services.moderation import (
    admin_stats,
    approve_profile,
    count_profiles,
    count_users,
    first_photo_file_ids,
    get_profile_admin,
    grant_credits,
    list_profiles,
    reject_profile,
    schedule_profile,
    search_users,
    set_user_blocked,
)
from app.services.notify import notify_user_published
from app.services.payments import (
    complete_ad_payment,
    complete_publish_payment,
    create_ad_payment,
    create_publish_payment,
)
from app.services.telegram_api import get_bot_username, send_message

router = APIRouter(prefix="/admin", tags=["admin"])


class PhotoOut(BaseModel):
    id: int
    position: int
    url: str


class ProfileListItem(BaseModel):
    id: int
    status: str
    name: str
    age: int
    gender: str | None
    city: str
    country: str
    telegram_username: str | None
    user_telegram_id: int | None
    user_id: int
    moderation_feedback: str | None
    scheduled_at: datetime | None
    paid_at: datetime | None
    published_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    photo_url: str | None


class ProfileDetail(ProfileListItem):
    height_cm: int
    has_children: bool
    wants_children: str
    marital_status: str
    profession: str
    hobbies: str
    about: str
    desired_partner: str
    age_min: int
    age_max: int
    cover_question_id: int | None
    cover_answer: str | None
    greeting_video_url: str | None = None
    photos: list[PhotoOut]
    message_credits: int
    is_blocked: bool


class RejectBody(BaseModel):
    feedback: str = Field(min_length=3, max_length=2000)


class ScheduleBody(BaseModel):
    scheduled_at: datetime


class CreditsBody(BaseModel):
    delta: int = Field(..., ge=-1000, le=1000)
    note: str | None = Field(default=None, max_length=512)


class UserOut(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    language_code: str
    gender: str | None
    message_credits: int
    is_blocked: bool
    profile_id: int | None
    profile_status: str | None
    profile_name: str | None
    photo_url: str | None = None


class PaymentOut(BaseModel):
    id: int
    user_id: int
    product: str
    status: str
    stars_amount: int
    related_profile_id: int | None
    created_at: datetime
    completed_at: datetime | None
    telegram_id: int | None = None
    username: str | None = None


def _photo_url(file_id: str) -> str:
    if file_id.startswith("local:"):
        return f"/media/profiles/{file_id.removeprefix('local:')}"
    return ""


def _list_item(profile: Profile, *, photo_file_id: str | None = None) -> ProfileListItem:
    user = profile.user
    file_id = photo_file_id
    if file_id is None and profile.photos:
        photos = sorted(profile.photos, key=lambda p: p.position)
        file_id = photos[0].file_id if photos else None
    return ProfileListItem(
        id=profile.id,
        status=profile.status,
        name=profile.name,
        age=profile.age,
        gender=profile.gender,
        city=profile.city,
        country=profile.country,
        telegram_username=profile.telegram_username,
        user_telegram_id=user.telegram_id if user else None,
        user_id=profile.user_id,
        moderation_feedback=profile.moderation_feedback,
        scheduled_at=profile.scheduled_at,
        paid_at=profile.paid_at,
        published_at=profile.published_at,
        approved_at=profile.approved_at,
        created_at=profile.created_at,
        photo_url=_photo_url(file_id) if file_id else None,
    )


def _detail(profile: Profile) -> ProfileDetail:
    photos = sorted(profile.photos or [], key=lambda p: p.position)
    first_id = photos[0].file_id if photos else None
    base = _list_item(profile, photo_file_id=first_id)
    user = profile.user
    return ProfileDetail(
        **base.model_dump(),
        height_cm=profile.height_cm,
        has_children=profile.has_children,
        wants_children=profile.wants_children,
        marital_status=profile.marital_status,
        profession=profile.profession,
        hobbies=profile.hobbies,
        about=profile.about,
        desired_partner=profile.desired_partner,
        age_min=profile.age_min,
        age_max=profile.age_max,
        cover_question_id=profile.cover_question_id,
        cover_answer=profile.cover_answer,
        greeting_video_url=video_url(profile.greeting_video_file_id),
        photos=[PhotoOut(id=p.id, position=p.position, url=_photo_url(p.file_id)) for p in photos],
        message_credits=user.message_credits if user else 0,
        is_blocked=user.is_blocked if user else False,
    )


@router.get("/ping")
async def admin_ping(auth: AuthContext = Depends(require_admin)) -> dict:
    return {"ok": True, "telegram_id": auth.telegram.id, "role": "admin"}


@router.get("/stats")
async def get_stats(
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await admin_stats(session)


class ProfileListPage(BaseModel):
    items: list[ProfileListItem]
    total: int
    limit: int
    offset: int
    has_more: bool


@router.get("/profiles", response_model=ProfileListPage)
async def admin_list_profiles(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ProfileListPage:
    status_arg: str | None = None
    statuses_arg: list[str] | None = None
    if status_filter == "moderation":
        status_arg = ProfileStatus.NEW.value
    elif status_filter == "queue":
        statuses_arg = [ProfileStatus.QUEUED.value, ProfileStatus.AWAITING_PAYMENT.value]
    elif status_filter:
        status_arg = status_filter

    total = await count_profiles(session, status=status_arg, statuses=statuses_arg)
    profiles = await list_profiles(
        session,
        status=status_arg,
        statuses=statuses_arg,
        limit=limit,
        offset=offset,
    )
    thumb_ids = await first_photo_file_ids(session, [p.id for p in profiles])
    items = [_list_item(p, photo_file_id=thumb_ids.get(p.id)) for p in profiles]
    return ProfileListPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items)) < total,
    )


@router.get("/profiles/{profile_id}", response_model=ProfileDetail)
async def admin_get_profile(
    profile_id: int,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ProfileDetail:
    profile = await get_profile_admin(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _detail(profile)


@router.post("/profiles/{profile_id}/approve", response_model=ProfileDetail)
async def admin_approve(
    profile_id: int,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ProfileDetail:
    profile = await get_profile_admin(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        profile = await approve_profile(session, settings, profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _detail(profile)


@router.post("/profiles/{profile_id}/reject", response_model=ProfileDetail)
async def admin_reject(
    profile_id: int,
    body: RejectBody,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ProfileDetail:
    profile = await get_profile_admin(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        profile = await reject_profile(session, settings, profile, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _detail(profile)


@router.post("/profiles/{profile_id}/schedule", response_model=ProfileDetail)
async def admin_schedule(
    profile_id: int,
    body: ScheduleBody,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ProfileDetail:
    profile = await get_profile_admin(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        profile = await schedule_profile(session, settings, profile, body.scheduled_at)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _detail(profile)


@router.post("/profiles/{profile_id}/mark-paid", response_model=ProfileDetail)
async def admin_mark_paid(
    profile_id: int,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ProfileDetail:
    """Dev/admin helper: mark publish payment completed without Stars."""
    profile = await get_profile_admin(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.status != ProfileStatus.AWAITING_PAYMENT.value:
        raise HTTPException(status_code=409, detail="Profile is not awaiting payment")

    result = await session.execute(select(User).where(User.id == profile.user_id))
    user = result.scalar_one()
    payment = await create_publish_payment(session, settings, user=user, profile=profile)
    await complete_publish_payment(
        session,
        settings,
        payment=payment,
        telegram_charge_id=f"admin:{auth.telegram.id}:{payment.id}",
    )
    profile = await get_profile_admin(session, profile_id)
    assert profile is not None
    return _detail(profile)


@router.post("/profiles/{profile_id}/publish-now", response_model=ProfileDetail)
async def admin_publish_now(
    profile_id: int,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ProfileDetail:
    profile = await get_profile_admin(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.status != ProfileStatus.QUEUED.value:
        raise HTTPException(status_code=409, detail="Only queued profiles can be published")
    if not profile.paid_at:
        raise HTTPException(status_code=409, detail="Profile is not paid")

    username = await get_bot_username(settings)
    try:
        profile = await publish_profile_to_channel(
            session, settings, profile_id, bot_username=username
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Publish failed: {exc}") from exc

    if profile.user:
        await notify_user_published(settings, user=profile.user, profile=profile)
    profile = await get_profile_admin(session, profile_id)
    assert profile is not None
    return _detail(profile)


class UserListPage(BaseModel):
    items: list[UserOut]
    total: int
    limit: int
    offset: int
    has_more: bool


@router.get("/users", response_model=UserListPage)
async def admin_users(
    q: str = Query(default=""),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserListPage:
    total = await count_users(session, query=q)
    users = await search_users(session, query=q, limit=limit, offset=offset)
    profile_ids = [u.profile.id for u in users if u.profile is not None]
    thumb_ids = await first_photo_file_ids(session, profile_ids)
    out: list[UserOut] = []
    for u in users:
        profile = u.profile
        file_id = thumb_ids.get(profile.id) if profile else None
        out.append(
            UserOut(
                id=u.id,
                telegram_id=u.telegram_id,
                username=u.telegram_username,
                first_name=u.telegram_first_name,
                language_code=u.language_code,
                gender=u.gender,
                message_credits=u.message_credits,
                is_blocked=u.is_blocked,
                profile_id=profile.id if profile else None,
                profile_status=profile.status if profile else None,
                profile_name=profile.name if profile else None,
                photo_url=_photo_url(file_id) if file_id else None,
            )
        )
    return UserListPage(
        items=out,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(out)) < total,
    )


@router.get("/users/{user_id}", response_model=UserOut)
async def admin_user_detail(
    user_id: int,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    result = await session.execute(
        select(User).where(User.id == user_id).options(selectinload(User.profile))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    profile = user.profile
    return UserOut(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.telegram_username,
        first_name=user.telegram_first_name,
        language_code=user.language_code,
        gender=user.gender,
        message_credits=user.message_credits,
        is_blocked=user.is_blocked,
        profile_id=profile.id if profile else None,
        profile_status=profile.status if profile else None,
        profile_name=profile.name if profile else None,
    )


@router.post("/users/{user_id}/block", response_model=UserOut)
async def admin_block_user(
    user_id: int,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> UserOut:
    result = await session.execute(
        select(User).where(User.id == user_id).options(selectinload(User.profile))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user = await set_user_blocked(session, user, True)
    try:
        await send_message(
            settings,
            user.telegram_id,
            "Ваш доступ к Italian Dreamers ограничен администратором.",
            parse_mode=None,
        )
    except Exception:
        pass
    profile = user.profile
    return UserOut(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.telegram_username,
        first_name=user.telegram_first_name,
        language_code=user.language_code,
        gender=user.gender,
        message_credits=user.message_credits,
        is_blocked=user.is_blocked,
        profile_id=profile.id if profile else None,
        profile_status=profile.status if profile else None,
        profile_name=profile.name if profile else None,
    )


@router.post("/users/{user_id}/unblock", response_model=UserOut)
async def admin_unblock_user(
    user_id: int,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    result = await session.execute(
        select(User).where(User.id == user_id).options(selectinload(User.profile))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user = await set_user_blocked(session, user, False)
    profile = user.profile
    return UserOut(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.telegram_username,
        first_name=user.telegram_first_name,
        language_code=user.language_code,
        gender=user.gender,
        message_credits=user.message_credits,
        is_blocked=user.is_blocked,
        profile_id=profile.id if profile else None,
        profile_status=profile.status if profile else None,
        profile_name=profile.name if profile else None,
    )


@router.post("/users/{user_id}/credits", response_model=UserOut)
async def admin_grant_credits(
    user_id: int,
    body: CreditsBody,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    result = await session.execute(
        select(User).where(User.id == user_id).options(selectinload(User.profile))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user = await grant_credits(session, user, body.delta, note=body.note)
    await session.refresh(user, attribute_names=["profile"])
    profile = user.profile
    return UserOut(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.telegram_username,
        first_name=user.telegram_first_name,
        language_code=user.language_code,
        gender=user.gender,
        message_credits=user.message_credits,
        is_blocked=user.is_blocked,
        profile_id=profile.id if profile else None,
        profile_status=profile.status if profile else None,
        profile_name=profile.name if profile else None,
    )


@router.get("/payments", response_model=list[PaymentOut])
async def admin_payments(
    limit: int = Query(default=50, ge=1, le=200),
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[PaymentOut]:
    result = await session.execute(
        select(Payment).options(selectinload(Payment.user)).order_by(Payment.id.desc()).limit(limit)
    )
    payments = list(result.scalars().all())
    return [
        PaymentOut(
            id=p.id,
            user_id=p.user_id,
            product=p.product,
            status=p.status,
            stars_amount=p.stars_amount,
            related_profile_id=p.related_profile_id,
            created_at=p.created_at,
            completed_at=p.completed_at,
            telegram_id=p.user.telegram_id if p.user else None,
            username=p.user.telegram_username if p.user else None,
        )
        for p in payments
    ]


class AdOut(BaseModel):
    id: int
    status: str
    title: str
    category: str
    body: str
    contact: str | None
    desired_date: str | None
    media_file_id: str | None
    moderation_feedback: str | None
    paid_at: datetime | None
    scheduled_at: datetime | None
    activated_at: datetime | None
    expires_at: datetime | None
    channel_message_id: int | None
    created_at: datetime
    user_id: int
    user_telegram_id: int | None
    username: str | None


class AdEditBody(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    category: str | None = Field(default=None, max_length=64)
    body: str | None = Field(default=None, min_length=10, max_length=2000)
    contact: str | None = Field(default=None, max_length=255)
    desired_date: str | None = Field(default=None, max_length=64)


class ComplaintOut(BaseModel):
    id: int
    status: str
    reason: str
    admin_note: str | None
    reporter_user_id: int
    reporter_telegram_id: int | None
    reported_user_id: int | None
    message_request_id: int | None
    created_at: datetime
    resolved_at: datetime | None


class ComplaintResolveBody(BaseModel):
    status: str = Field(pattern="^(reviewed|resolved|dismissed)$")
    admin_note: str | None = Field(default=None, max_length=2000)


def _ad_out(ad: AdRequest) -> AdOut:
    user = ad.user
    return AdOut(
        id=ad.id,
        status=ad.status,
        title=ad.title,
        category=ad.category,
        body=ad.body,
        contact=ad.contact,
        desired_date=ad.desired_date,
        media_file_id=ad.media_file_id,
        moderation_feedback=ad.moderation_feedback,
        paid_at=ad.paid_at,
        scheduled_at=ad.scheduled_at,
        activated_at=ad.activated_at,
        expires_at=ad.expires_at,
        channel_message_id=ad.channel_message_id,
        created_at=ad.created_at,
        user_id=ad.user_id,
        user_telegram_id=user.telegram_id if user else None,
        username=user.telegram_username if user else None,
    )


def _complaint_out(c: Complaint) -> ComplaintOut:
    return ComplaintOut(
        id=c.id,
        status=c.status,
        reason=c.reason,
        admin_note=c.admin_note,
        reporter_user_id=c.reporter_user_id,
        reporter_telegram_id=c.reporter.telegram_id if c.reporter else None,
        reported_user_id=c.reported_user_id,
        message_request_id=c.message_request_id,
        created_at=c.created_at,
        resolved_at=c.resolved_at,
    )


@router.get("/ads", response_model=list[AdOut])
async def admin_list_ads(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AdOut]:
    if status_filter == "queue":
        ads = await list_ads(
            session,
            statuses=["awaiting_payment", "queued", "active"],
            limit=limit,
            offset=offset,
        )
    elif status_filter:
        ads = await list_ads(session, status=status_filter, limit=limit, offset=offset)
    else:
        ads = await list_ads(session, limit=limit, offset=offset)
    return [_ad_out(a) for a in ads]


@router.get("/ads/{ad_id}", response_model=AdOut)
async def admin_get_ad(
    ad_id: int,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AdOut:
    ad = await get_ad(session, ad_id)
    if ad is None:
        raise HTTPException(status_code=404, detail="Ad not found")
    return _ad_out(ad)


@router.post("/ads/{ad_id}/approve", response_model=AdOut)
async def admin_approve_ad(
    ad_id: int,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AdOut:
    ad = await get_ad(session, ad_id)
    if ad is None:
        raise HTTPException(status_code=404, detail="Ad not found")
    try:
        ad = await approve_ad(session, settings, ad)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _ad_out(ad)


@router.post("/ads/{ad_id}/reject", response_model=AdOut)
async def admin_reject_ad(
    ad_id: int,
    body: RejectBody,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AdOut:
    ad = await get_ad(session, ad_id)
    if ad is None:
        raise HTTPException(status_code=404, detail="Ad not found")
    try:
        ad = await reject_ad(session, settings, ad, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _ad_out(ad)


@router.patch("/ads/{ad_id}", response_model=AdOut)
async def admin_edit_ad(
    ad_id: int,
    body: AdEditBody,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AdOut:
    ad = await get_ad(session, ad_id)
    if ad is None:
        raise HTTPException(status_code=404, detail="Ad not found")
    try:
        ad = await update_ad_request(
            session,
            ad,
            title=body.title,
            category=body.category,
            body=body.body,
            contact=body.contact,
            desired_date=body.desired_date,
        )
    except AdServiceError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
    return _ad_out(ad)


@router.post("/ads/{ad_id}/mark-paid", response_model=AdOut)
async def admin_mark_ad_paid(
    ad_id: int,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AdOut:
    ad = await get_ad(session, ad_id)
    if ad is None:
        raise HTTPException(status_code=404, detail="Ad not found")
    if ad.status != "awaiting_payment":
        raise HTTPException(status_code=409, detail="Ad is not awaiting payment")
    result = await session.execute(select(User).where(User.id == ad.user_id))
    user = result.scalar_one()
    payment = await create_ad_payment(session, settings, user=user, ad=ad)
    await complete_ad_payment(
        session,
        settings,
        payment=payment,
        telegram_charge_id=f"admin:{auth.telegram.id}:{payment.id}",
    )
    ad = await get_ad(session, ad_id)
    assert ad is not None
    return _ad_out(ad)


@router.post("/ads/{ad_id}/activate-now", response_model=AdOut)
async def admin_activate_ad_now(
    ad_id: int,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AdOut:
    ad = await get_ad(session, ad_id)
    if ad is None:
        raise HTTPException(status_code=404, detail="Ad not found")
    try:
        ad = await activate_ad(session, settings, ad)
    except AdServiceError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message}) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Activate failed: {exc}") from exc
    return _ad_out(ad)


@router.get("/complaints", response_model=list[ComplaintOut])
async def admin_list_complaints(
    status_filter: str | None = Query(default="open", alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ComplaintOut]:
    status_arg = None if status_filter in {None, "", "all"} else status_filter
    items = await list_complaints(session, status=status_arg, limit=limit)
    return [_complaint_out(c) for c in items]


@router.post("/complaints/{complaint_id}/resolve", response_model=ComplaintOut)
async def admin_resolve_complaint(
    complaint_id: int,
    body: ComplaintResolveBody,
    _auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> ComplaintOut:
    complaint = await get_complaint(session, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    complaint = await resolve_complaint(
        session, complaint, status=body.status, admin_note=body.admin_note
    )
    return _complaint_out(complaint)
