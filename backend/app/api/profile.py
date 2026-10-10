"""User profile CRUD + photo upload + submit for moderation."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth_context
from app.config import Settings, get_settings
from app.database import get_session
from app.models import (
    Gender,
    MaritalStatus,
    Profile,
    ProfilePhoto,
    ProfileStatus,
    PublicationOption,
    WantsChildren,
)
from app.services.cover_questions import COVER_QUESTIONS
from app.services.greeting_video import (
    MAX_VIDEO_BYTES,
    MEDIA_VIDEOS,
    VIDEO_EXTENSIONS,
    normalize_to_mp4,
    remove_video,
    video_url,
)
from app.services.notify import notify_admins_profile_submitted
from app.services.payments import create_publish_payment, send_publish_invoice
from app.services.profiles import (
    CONTACT_CHECKED_FIELDS,
    assert_editable,
    fields_with_contacts,
    get_or_create_draft,
    get_user_profile,
    validate_for_submit,
)

router = APIRouter(prefix="/me/profile", tags=["profile"])

MEDIA_ROOT = Path(__file__).resolve().parents[2] / "media" / "profiles"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
REQUIRED_PHOTOS = 3


class PhotoOut(BaseModel):
    id: int
    position: int
    url: str


class ProfileOut(BaseModel):
    id: int
    status: str
    name: str
    age: int
    age_min: int
    age_max: int
    height_cm: int
    has_children: bool
    gender: str | None
    wants_children: str
    marital_status: str
    country: str
    city: str
    profession: str
    hobbies: str
    about: str
    desired_partner: str
    telegram_username: str | None
    personal_data_agreement: bool
    cover_question_id: int | None
    cover_answer: str | None
    greeting_video_url: str | None = None
    moderation_feedback: str | None
    scheduled_at: datetime | None = None
    paid_at: datetime | None = None
    published_at: datetime | None = None
    photos: list[PhotoOut]
    editable: bool
    can_pay: bool = False
    channel_post_url: str | None = None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    age: int | None = Field(default=None, ge=18, le=99)
    age_min: int | None = Field(default=None, ge=18, le=99)
    age_max: int | None = Field(default=None, ge=18, le=99)
    height_cm: int | None = Field(default=None, ge=140, le=210)
    has_children: bool | None = None
    gender: Gender | None = None
    wants_children: WantsChildren | None = None
    marital_status: MaritalStatus | None = None
    country: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=255)
    profession: str | None = Field(default=None, max_length=255)
    hobbies: str | None = Field(default=None, max_length=300)
    about: str | None = None
    desired_partner: str | None = None
    telegram_username: str | None = Field(default=None, max_length=255)
    personal_data_agreement: bool | None = None
    cover_question_id: int | None = Field(default=None, ge=1, le=9)
    cover_answer: str | None = Field(default=None, max_length=70)


class CoverQuestionsOut(BaseModel):
    questions: list[dict]


def _photo_url(file_id: str) -> str:
    if file_id.startswith("local:"):
        return f"/media/profiles/{file_id.removeprefix('local:')}"
    return ""


def _channel_post_url(profile: Profile) -> str | None:
    if profile.status != ProfileStatus.PUBLISHED.value or not profile.channel_message_id:
        return None
    channel = str(get_settings().channel_id)
    if not channel.startswith("-100"):
        return None
    # t.me/c/ links open for any channel member, public or private
    return f"https://t.me/c/{channel.removeprefix('-100')}/{profile.channel_message_id}"


def _serialize(profile: Profile) -> ProfileOut:
    photos = sorted(profile.photos or [], key=lambda p: p.position)
    return ProfileOut(
        id=profile.id,
        status=profile.status,
        name=profile.name,
        age=profile.age,
        age_min=profile.age_min,
        age_max=profile.age_max,
        height_cm=profile.height_cm,
        has_children=profile.has_children,
        gender=profile.gender,
        wants_children=profile.wants_children,
        marital_status=profile.marital_status,
        country=profile.country,
        city=profile.city,
        profession=profile.profession,
        hobbies=profile.hobbies,
        about=profile.about,
        desired_partner=profile.desired_partner,
        telegram_username=profile.telegram_username,
        personal_data_agreement=profile.personal_data_agreement,
        cover_question_id=profile.cover_question_id,
        cover_answer=profile.cover_answer,
        greeting_video_url=video_url(profile.greeting_video_file_id),
        moderation_feedback=profile.moderation_feedback,
        scheduled_at=profile.scheduled_at,
        paid_at=profile.paid_at,
        published_at=profile.published_at,
        photos=[
            PhotoOut(id=p.id, position=p.position, url=_photo_url(p.file_id)) for p in photos
        ],
        editable=profile.status in {ProfileStatus.DRAFT.value, ProfileStatus.REJECTED.value},
        can_pay=profile.status == ProfileStatus.AWAITING_PAYMENT.value,
        channel_post_url=_channel_post_url(profile),
    )


def _normalize_username(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip().lstrip("@")
    return value or None


@router.get("/cover-questions", response_model=CoverQuestionsOut)
async def list_cover_questions() -> CoverQuestionsOut:
    items = [
        {"id": qid, "ru": texts["ru"], "it": texts["it"]}
        for qid, texts in COVER_QUESTIONS.items()
    ]
    return CoverQuestionsOut(questions=items)


@router.get("", response_model=ProfileOut)
async def get_profile(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await get_or_create_draft(session, auth.user)
    return _serialize(profile)


@router.put("", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await get_or_create_draft(session, auth.user)
    try:
        assert_editable(profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    data = body.model_dump(exclude_unset=True)
    if "telegram_username" in data:
        data["telegram_username"] = _normalize_username(data["telegram_username"])
    if "gender" in data and data["gender"] is not None:
        data["gender"] = data["gender"].value if hasattr(data["gender"], "value") else data["gender"]
        auth.user.gender = data["gender"]
        session.add(auth.user)
    if "wants_children" in data and data["wants_children"] is not None:
        data["wants_children"] = (
            data["wants_children"].value
            if hasattr(data["wants_children"], "value")
            else data["wants_children"]
        )
    if "marital_status" in data and data["marital_status"] is not None:
        data["marital_status"] = (
            data["marital_status"].value
            if hasattr(data["marital_status"], "value")
            else data["marital_status"]
        )
    if "cover_answer" in data and data["cover_answer"] is not None:
        data["cover_answer"] = data["cover_answer"].strip()
    contact_fields = fields_with_contacts(data)
    if contact_fields:
        raise HTTPException(
            status_code=400,
            detail={"code": "contact_forbidden", "message": "Contact details are not allowed", "fields": contact_fields},
        )

    for key, value in data.items():
        setattr(profile, key, value)

    if profile.status == ProfileStatus.REJECTED.value:
        profile.status = ProfileStatus.DRAFT.value
        profile.moderation_feedback = None

    session.add(profile)
    await session.commit()
    profile = await get_user_profile(session, auth.user.id)
    assert profile is not None
    return _serialize(profile)


@router.post("/photos", response_model=ProfileOut)
async def upload_photo(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await get_or_create_draft(session, auth.user)
    try:
        assert_editable(profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if len(profile.photos) >= REQUIRED_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Maximum {REQUIRED_PHOTOS} photos")

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG/WebP images allowed")

    ext = ".jpg"
    if "png" in content_type:
        ext = ".png"
    elif "webp" in content_type:
        ext = ".webp"

    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 8MB)")
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = f"{uuid.uuid4().hex}{ext}"
    dest = MEDIA_ROOT / filename
    dest.write_bytes(raw)

    positions = [p.position for p in profile.photos]
    next_pos = max(positions) + 1 if positions else 0
    photo = ProfilePhoto(
        profile_id=profile.id,
        file_id=f"local:{filename}",
        file_unique_id=filename,
        position=next_pos,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(profile, attribute_names=["photos"])
    return _serialize(profile)


@router.delete("/photos/{photo_id}", response_model=ProfileOut)
async def delete_photo(
    photo_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await get_or_create_draft(session, auth.user)
    try:
        assert_editable(profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    target = next((p for p in profile.photos if p.id == photo_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    if target.file_id.startswith("local:"):
        path = MEDIA_ROOT / target.file_id.removeprefix("local:")
        if path.exists():
            path.unlink(missing_ok=True)

    await session.delete(target)
    await session.flush()
    remaining = sorted([p for p in profile.photos if p.id != photo_id], key=lambda p: p.position)
    for idx, photo in enumerate(remaining):
        photo.position = idx
        session.add(photo)
    await session.commit()
    await session.refresh(profile, attribute_names=["photos"])
    return _serialize(profile)


@router.post("/video", response_model=ProfileOut)
async def upload_greeting_video(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await get_or_create_draft(session, auth.user)
    try:
        assert_editable(profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    if not content_type.startswith("video/") and suffix not in VIDEO_EXTENSIONS.values():
        raise HTTPException(status_code=400, detail="Only video files allowed")
    ext = VIDEO_EXTENSIONS.get(content_type) or suffix or ".mp4"

    dest = MEDIA_VIDEOS / f"{uuid.uuid4().hex}{ext}"
    with dest.open("wb") as fh:
        shutil.copyfileobj(file.file, fh, length=1024 * 1024)
    size = dest.stat().st_size
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty file")
    if size > MAX_VIDEO_BYTES:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail="video_too_large")

    final = await normalize_to_mp4(dest)
    previous = profile.greeting_video_file_id
    profile.greeting_video_file_id = f"local:{final.name}"
    session.add(profile)
    await session.commit()
    remove_video(previous)
    profile = await get_user_profile(session, auth.user.id)
    assert profile is not None
    return _serialize(profile)


@router.delete("/video", response_model=ProfileOut)
async def delete_greeting_video(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ProfileOut:
    profile = await get_or_create_draft(session, auth.user)
    try:
        assert_editable(profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    previous = profile.greeting_video_file_id
    profile.greeting_video_file_id = None
    session.add(profile)
    await session.commit()
    remove_video(previous)
    profile = await get_user_profile(session, auth.user.id)
    assert profile is not None
    return _serialize(profile)


@router.post("/submit", response_model=ProfileOut)
async def submit_profile(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ProfileOut:
    profile = await get_or_create_draft(session, auth.user)
    try:
        assert_editable(profile)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not profile.telegram_username and auth.user.telegram_username:
        profile.telegram_username = auth.user.telegram_username
    if not profile.gender and auth.user.gender:
        profile.gender = auth.user.gender

    contact_fields = fields_with_contacts({key: getattr(profile, key) for key in CONTACT_CHECKED_FIELDS})
    if contact_fields:
        raise HTTPException(
            status_code=400,
            detail={"code": "contact_forbidden", "message": "Contact details are not allowed", "fields": contact_fields},
        )

    errors = validate_for_submit(profile)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "Profile incomplete", "fields": errors, "required_photos": REQUIRED_PHOTOS},
        )

    profile.status = ProfileStatus.NEW.value
    profile.publication_option = PublicationOption.STANDARD.value
    session.add(profile)
    await session.commit()
    profile = await get_user_profile(session, auth.user.id)
    assert profile is not None

    await notify_admins_profile_submitted(settings, user=auth.user, profile=profile)
    return _serialize(profile)


@router.post("/pay")
async def request_publish_invoice(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    profile = await get_user_profile(session, auth.user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.status != ProfileStatus.AWAITING_PAYMENT.value:
        raise HTTPException(status_code=409, detail="Profile is not awaiting payment")

    payment = await create_publish_payment(session, settings, user=auth.user, profile=profile)
    await send_publish_invoice(settings, user=auth.user, profile=profile, payment=payment)
    return {
        "ok": True,
        "payment_id": payment.id,
        "stars": payment.stars_amount,
        "message": "Invoice sent to Telegram chat",
    }
