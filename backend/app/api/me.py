from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth_context
from app.config import Settings, get_settings
from app.database import get_session
from app.models import LanguageCode, Profile, ProfileStatus
from app.services.entitlements import active_subscription, has_unlimited, is_top_now
from app.services.legacy import LegacyServiceError, claim_legacy
from app.services.payments import (
    cancel_unlimited_subscription,
    create_catalog_top_payment,
    create_unlimited_payment,
    send_catalog_top_invoice,
    send_unlimited_invoice,
)
from app.services.username_nudge import CHECK_BUTTON, MISS_TEXT, OK_TEXT, check_and_store_username, _lang
from app.services.telegram_api import TelegramApiError
from app.services.verification import VerificationError, submit_selfie
from app.services.vision import photo_has_person


def _invoice_or_502(exc: TelegramApiError) -> HTTPException:
    return HTTPException(status_code=502, detail="invoice_failed")

router = APIRouter(prefix="/me", tags=["me"])


class MeResponse(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    language_code: str
    gender: str | None
    message_credits: int
    is_admin: bool
    is_blocked: bool
    soft_ban_until: datetime | None
    is_soft_banned: bool
    profile_status: str | None
    profile_id: int | None
    has_username: bool = False
    bot_write_access: bool = False
    has_unlimited: bool = False
    unlimited_until: datetime | None = None
    verification_status: str | None = None
    is_top: bool = False
    top_until: datetime | None = None


class LanguageUpdate(BaseModel):
    language_code: LanguageCode


class GenderUpdate(BaseModel):
    gender: str = Field(pattern="^(male|female)$")


class PlatformUpdate(BaseModel):
    platform: str = Field(max_length=32)


class WriteAccessUpdate(BaseModel):
    granted: bool


async def _build_me(auth: AuthContext, session: AsyncSession) -> MeResponse:
    now = datetime.now(timezone.utc)
    soft_ban = auth.user.soft_ban_until
    is_soft_banned = bool(soft_ban and soft_ban > now)
    result = await session.execute(select(Profile).where(Profile.user_id == auth.user.id))
    profile = result.scalar_one_or_none()
    sub = await active_subscription(session, auth.user.id)
    return MeResponse(
        id=auth.user.id,
        telegram_id=auth.user.telegram_id,
        username=auth.user.telegram_username,
        first_name=auth.user.telegram_first_name,
        language_code=auth.user.language_code,
        gender=auth.user.gender,
        message_credits=auth.user.message_credits,
        is_admin=auth.is_admin,
        is_blocked=auth.user.is_blocked,
        soft_ban_until=auth.user.soft_ban_until,
        is_soft_banned=is_soft_banned,
        profile_status=profile.status if profile else None,
        profile_id=profile.id if profile else None,
        has_username=bool((auth.user.telegram_username or "").strip()),
        bot_write_access=bool(auth.user.bot_write_access),
        has_unlimited=sub is not None,
        unlimited_until=sub.expires_at if sub else None,
        verification_status=profile.verification_status if profile else None,
        is_top=is_top_now(profile) if profile else False,
        top_until=profile.top_until if profile else None,
    )


@router.get("", response_model=MeResponse)
async def get_me(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    return await _build_me(auth, session)


@router.patch("/language", response_model=MeResponse)
async def update_language(
    body: LanguageUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    auth.user.language_code = body.language_code.value
    session.add(auth.user)
    await session.commit()
    await session.refresh(auth.user)
    return await _build_me(auth, session)


@router.patch("/gender", response_model=MeResponse)
async def update_gender(
    body: GenderUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    auth.user.gender = body.gender
    session.add(auth.user)
    await session.commit()
    await session.refresh(auth.user)
    return await _build_me(auth, session)


@router.patch("/platform", response_model=MeResponse)
async def update_platform(
    body: PlatformUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    auth.user.telegram_platform = (body.platform or "").strip().lower()[:32] or None
    session.add(auth.user)
    await session.commit()
    await session.refresh(auth.user)
    return await _build_me(auth, session)


@router.patch("/write-access", response_model=MeResponse)
async def update_write_access(
    body: WriteAccessUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    auth.user.bot_write_access = body.granted
    if body.granted:
        auth.user.bot_write_access_at = datetime.now(timezone.utc)
    session.add(auth.user)
    await session.commit()
    await session.refresh(auth.user)
    return await _build_me(auth, session)


@router.post("/username-check")
async def username_check(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    lang = _lang(auth.user)
    username = await check_and_store_username(session, settings, user=auth.user)
    if username:
        return {"ok": True, "username": username, "message": OK_TEXT[lang].format(username=username)}
    return {"ok": False, "username": None, "message": MISS_TEXT[lang], "button": CHECK_BUTTON[lang]}


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


@router.post("/unlimited")
async def buy_unlimited(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    if await has_unlimited(session, auth.user.id):
        return {"ok": True, "already": True}
    payment = await create_unlimited_payment(session, settings, user=auth.user)
    try:
        await send_unlimited_invoice(settings, user=auth.user, payment=payment)
    except TelegramApiError as exc:
        raise _invoice_or_502(exc) from exc
    return {"ok": True, "payment_id": payment.id, "stars": payment.stars_amount}


@router.post("/unlimited/cancel")
async def cancel_unlimited(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    sub = await cancel_unlimited_subscription(session, settings, user=auth.user)
    if sub is None:
        raise HTTPException(status_code=404, detail="No active subscription")
    return {"ok": True, "expires_at": sub.expires_at}


@router.post("/catalog-top")
async def buy_catalog_top(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    result = await session.execute(select(Profile).where(Profile.user_id == auth.user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.status not in {ProfileStatus.QUEUED.value, ProfileStatus.PUBLISHED.value}:
        raise HTTPException(status_code=409, detail="Profile is not in catalog")
    if await has_unlimited(session, auth.user.id):
        return {"ok": True, "already": True, "included": True}
    payment = await create_catalog_top_payment(session, settings, user=auth.user, profile=profile)
    try:
        await send_catalog_top_invoice(settings, user=auth.user, profile=profile, payment=payment)
    except TelegramApiError as exc:
        raise _invoice_or_502(exc) from exc
    return {"ok": True, "payment_id": payment.id, "stars": payment.stars_amount}


@router.post("/verification")
async def upload_verification_selfie(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    from app.services.verification import VERIFY_MEDIA

    result = await session.execute(select(Profile).where(Profile.user_id == auth.user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG/WebP images allowed")
    raw = await file.read()
    if not raw or len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Invalid file")
    if not await photo_has_person(
        raw, mime=content_type or "image/jpeg", api_key=settings.translation_api_key, model=settings.openai_vision_model
    ):
        raise HTTPException(status_code=400, detail="selfie_no_person")
    ext = ".jpg"
    if "png" in content_type:
        ext = ".png"
    elif "webp" in content_type:
        ext = ".webp"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest: Path = VERIFY_MEDIA / filename
    dest.write_bytes(raw)
    try:
        profile = await submit_selfie(session, profile, f"local:{filename}")
    except VerificationError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail=exc.code) from exc
    return {"ok": True, "verification_status": profile.verification_status}


@router.post("/legacy/{token}")
async def activate_legacy(
    token: str,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        row = await claim_legacy(session, token=token, user=auth.user)
    except LegacyServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc
    return {"ok": True, "id": row.id, "name": row.name}
