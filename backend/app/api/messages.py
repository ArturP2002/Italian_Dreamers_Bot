"""Inbox, letter form, unlock, bilingual chat, credit invoices."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth_context
from app.config import Settings, get_settings
from app.database import get_session
from app.models import MessageRequest, MessageRequestStatus, ProfileStatus, User
from app.services.messages import (
    MessageServiceError,
    create_message_request,
    get_message_request,
    get_published_profile,
    inbox_pending_count,
    list_chat_messages,
    list_inbox,
    reject_message_request,
    reply_message_request,
    send_chat_message,
    unlock_with_credit,
)
from app.services.payments import create_credit_payment, send_credit_invoice
from app.services.profiles import get_user_profile
from app.services.referrals import claim_referral, count_invited, ensure_referral_code, referral_link

router = APIRouter(tags=["messages"])

MEDIA_ROOT = Path(__file__).resolve().parents[2] / "media" / "letters"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


class ChatMessageOut(BaseModel):
    id: int
    sender_user_id: int
    text: str
    text_translated: str | None
    created_at: datetime
    is_mine: bool


class MessageRequestOut(BaseModel):
    id: int
    status: str
    direction: str  # incoming | outgoing
    text: str
    text_translated: str | None
    reply_text: str | None
    reply_text_translated: str | None
    sender_name: str | None
    sender_age: int | None
    sender_photo_url: str | None
    profile_id: int
    profile_name: str | None
    profile_age: int | None
    profile_photo_url: str | None
    profile_city: str | None
    profile_about: str | None
    profile_dream: str | None
    counterpart_username: str | None
    counterpart_telegram_link: str | None
    unlocked_at: datetime | None
    created_at: datetime
    responded_at: datetime | None
    can_reply: bool
    can_reject: bool
    can_unlock: bool
    can_chat: bool
    message_credits: int


class InboxOut(BaseModel):
    items: list[MessageRequestOut]
    pending_incoming: int
    message_credits: int


class SenderIdentityOut(BaseModel):
    source: str  # profile | saved
    name: str
    age: int
    city: str | None
    photo_url: str | None


class WriteTargetOut(BaseModel):
    profile_id: int
    name: str
    age: int
    city: str
    photo_url: str | None
    gender: str | None
    sender: SenderIdentityOut | None = None


class ChatOut(BaseModel):
    request_id: int
    status: str
    messages: list[ChatMessageOut]
    counterpart_name: str | None
    counterpart_telegram_link: str | None
    can_send: bool


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=1200)


class ChatSendIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class BuyCreditsIn(BaseModel):
    pack: bool = False
    message_request_id: int | None = None


class ReferralOut(BaseModel):
    code: str
    link: str
    referred_by_user_id: int | None
    invited_count: int = 0
    bonus_credits: int = 0


def _photo_url(file_id: str | None) -> str | None:
    if not file_id:
        return None
    if file_id.startswith("local:"):
        rel = file_id.removeprefix("local:")
        if rel.startswith("letters/"):
            return f"/media/{rel}"
        return f"/media/profiles/{rel}"
    return None


APPROVED_PROFILE_STATUSES = {
    ProfileStatus.APPROVED.value,
    ProfileStatus.AWAITING_PAYMENT.value,
    ProfileStatus.QUEUED.value,
    ProfileStatus.PUBLISHED.value,
}
STATED_NAME_MAX = 20


@dataclass
class _SenderIdentity:
    source: str
    name: str
    age: int
    city: str | None
    photo_file_id: str | None


async def _resolve_sender_identity(session: AsyncSession, user: User) -> _SenderIdentity | None:
    profile = await get_user_profile(session, user.id)
    if profile is not None and profile.status in APPROVED_PROFILE_STATUSES:
        photos = sorted(profile.photos or [], key=lambda p: p.position)
        return _SenderIdentity(
            source="profile",
            name=profile.name,
            age=profile.age,
            city=profile.city,
            photo_file_id=photos[0].file_id if photos else None,
        )
    if user.stated_name and user.stated_age:
        return _SenderIdentity(
            source="saved",
            name=user.stated_name,
            age=user.stated_age,
            city=None,
            photo_file_id=user.stated_photo_file_id,
        )
    return None


def _tg_link(username: str | None) -> str | None:
    if not username:
        return None
    clean = username.strip().lstrip("@")
    return f"https://t.me/{clean}" if clean else None


def _raise_service(exc: MessageServiceError) -> None:
    mapping = {
        "blocked": status.HTTP_403_FORBIDDEN,
        "soft_banned": status.HTTP_403_FORBIDDEN,
        "forbidden": status.HTTP_403_FORBIDDEN,
        "self": status.HTTP_400_BAD_REQUEST,
        "no_username": status.HTTP_400_BAD_REQUEST,
        "duplicate": status.HTTP_409_CONFLICT,
        "pending_limit": status.HTTP_429_TOO_MANY_REQUESTS,
        "rate_hour": status.HTTP_429_TOO_MANY_REQUESTS,
        "rate_day": status.HTTP_429_TOO_MANY_REQUESTS,
        "contact_forbidden": status.HTTP_400_BAD_REQUEST,
        "text_short": status.HTTP_400_BAD_REQUEST,
        "text_long": status.HTTP_400_BAD_REQUEST,
        "name_invalid": status.HTTP_400_BAD_REQUEST,
        "age_invalid": status.HTTP_400_BAD_REQUEST,
        "bad_status": status.HTTP_409_CONFLICT,
        "no_credits": status.HTTP_402_PAYMENT_REQUIRED,
        "locked": status.HTTP_409_CONFLICT,
    }
    raise HTTPException(status_code=mapping.get(exc.code, 400), detail={"code": exc.code, "message": exc.message})


def _serialize_request(mr: MessageRequest, viewer: User) -> MessageRequestOut:
    profile = mr.profile
    is_incoming = bool(profile and profile.user_id == viewer.id)
    direction = "incoming" if is_incoming else "outgoing"

    profile_photo = None
    if profile and profile.photos:
        first = sorted(profile.photos, key=lambda p: p.position)[0]
        profile_photo = _photo_url(first.file_id)

    if is_incoming:
        counterpart_username = mr.sender.telegram_username if mr.sender else None
    else:
        counterpart_username = (
            (profile.telegram_username if profile else None)
            or (profile.user.telegram_username if profile and profile.user else None)
        )

    status_val = mr.status
    can_chat = status_val in {
        MessageRequestStatus.UNLOCKED.value,
        MessageRequestStatus.CHATTING.value,
    }
    return MessageRequestOut(
        id=mr.id,
        status=status_val,
        direction=direction,
        text=mr.text,
        text_translated=mr.text_translated,
        reply_text=mr.reply_text,
        reply_text_translated=mr.reply_text_translated,
        sender_name=mr.sender_name,
        sender_age=mr.sender_age,
        sender_photo_url=_photo_url(mr.sender_photo_file_id),
        profile_id=mr.profile_id,
        profile_name=profile.name if profile else None,
        profile_age=profile.age if profile else None,
        profile_photo_url=profile_photo,
        profile_city=profile.city if profile else None,
        profile_about=profile.about if profile else None,
        profile_dream=profile.dream_location if profile else None,
        counterpart_username=counterpart_username,
        counterpart_telegram_link=_tg_link(counterpart_username),
        unlocked_at=mr.unlocked_at,
        created_at=mr.created_at,
        responded_at=mr.responded_at,
        can_reply=is_incoming and status_val == MessageRequestStatus.PENDING.value,
        can_reject=is_incoming and status_val == MessageRequestStatus.PENDING.value,
        can_unlock=(
            not is_incoming
            and status_val == MessageRequestStatus.REPLIED.value
        ),
        can_chat=can_chat,
        message_credits=viewer.message_credits,
    )


@router.get("/messages/inbox", response_model=InboxOut)
async def get_inbox(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> InboxOut:
    items = await list_inbox(session, auth.user)
    pending = await inbox_pending_count(session, auth.user)
    return InboxOut(
        items=[_serialize_request(mr, auth.user) for mr in items],
        pending_incoming=pending,
        message_credits=auth.user.message_credits,
    )


@router.get("/messages/write-target/{profile_id}", response_model=WriteTargetOut)
async def write_target(
    profile_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> WriteTargetOut:
    profile = await get_published_profile(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found or not published")
    photo = None
    if profile.photos:
        first = sorted(profile.photos, key=lambda p: p.position)[0]
        photo = _photo_url(first.file_id)
    identity = await _resolve_sender_identity(session, auth.user)
    return WriteTargetOut(
        profile_id=profile.id,
        name=profile.name,
        age=profile.age,
        city=profile.city,
        photo_url=photo,
        gender=profile.gender,
        sender=SenderIdentityOut(
            source=identity.source,
            name=identity.name,
            age=identity.age,
            city=identity.city,
            photo_url=_photo_url(identity.photo_file_id),
        )
        if identity
        else None,
    )


@router.post("/messages", response_model=MessageRequestOut, status_code=201)
async def create_letter(
    profile_id: int = Form(...),
    text: str = Form(...),
    sender_name: str | None = Form(None),
    sender_age: int | None = Form(None),
    photo: UploadFile | None = File(None),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> MessageRequestOut:
    if auth.user.is_blocked:
        raise HTTPException(status_code=403, detail="Blocked")
    profile = await get_published_profile(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found or not published")

    photo_file_id: str | None = None
    if photo is not None and photo.filename:
        content_type = (photo.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Invalid image type")
        raw = await photo.read()
        if len(raw) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large")
        ext = "jpg"
        if "png" in content_type:
            ext = "png"
        elif "webp" in content_type:
            ext = "webp"
        name = f"{auth.user.id}_{uuid.uuid4().hex[:12]}.{ext}"
        dest = MEDIA_ROOT / name
        dest.write_bytes(raw)
        photo_file_id = f"local:letters/{name}"

    identity = await _resolve_sender_identity(session, auth.user)
    if identity is not None:
        name_value, age_value = identity.name, identity.age
        photo_file_id = photo_file_id or identity.photo_file_id
    else:
        name_value = (sender_name or "").strip()
        if not name_value or len(name_value) > STATED_NAME_MAX:
            raise HTTPException(
                status_code=400, detail={"code": "name_invalid", "message": "Invalid sender name"}
            )
        if sender_age is None:
            raise HTTPException(
                status_code=400, detail={"code": "age_invalid", "message": "Invalid sender age"}
            )
        age_value = sender_age

    try:
        mr = await create_message_request(
            session,
            settings,
            sender=auth.user,
            profile=profile,
            text=text,
            sender_name=name_value,
            sender_age=age_value,
            sender_photo_file_id=photo_file_id,
            remember_identity=identity is None or identity.source == "saved",
        )
    except MessageServiceError as exc:
        _raise_service(exc)
    return _serialize_request(mr, auth.user)


@router.get("/messages/{request_id}", response_model=MessageRequestOut)
async def get_letter(
    request_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> MessageRequestOut:
    mr = await get_message_request(session, request_id, for_user=auth.user)
    if mr is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _serialize_request(mr, auth.user)


@router.post("/messages/{request_id}/reject", response_model=MessageRequestOut)
async def reject_letter(
    request_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> MessageRequestOut:
    mr = await get_message_request(session, request_id, for_user=auth.user)
    if mr is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        mr = await reject_message_request(session, settings, mr=mr, actor=auth.user)
    except MessageServiceError as exc:
        _raise_service(exc)
    return _serialize_request(mr, auth.user)


@router.post("/messages/{request_id}/reply", response_model=MessageRequestOut)
async def reply_letter(
    request_id: int,
    body: ReplyIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> MessageRequestOut:
    mr = await get_message_request(session, request_id, for_user=auth.user)
    if mr is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        mr = await reply_message_request(
            session, settings, mr=mr, actor=auth.user, reply_text=body.text
        )
    except MessageServiceError as exc:
        _raise_service(exc)
    return _serialize_request(mr, auth.user)


@router.post("/messages/{request_id}/unlock", response_model=MessageRequestOut)
async def unlock_letter(
    request_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> MessageRequestOut:
    mr = await get_message_request(session, request_id, for_user=auth.user)
    if mr is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        mr = await unlock_with_credit(session, settings, mr=mr, actor=auth.user)
    except MessageServiceError as exc:
        _raise_service(exc)
    await session.refresh(auth.user)
    return _serialize_request(mr, auth.user)


@router.post("/messages/buy-credits")
async def buy_credits(
    body: BuyCreditsIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    if body.message_request_id is not None:
        mr = await get_message_request(session, body.message_request_id, for_user=auth.user)
        if mr is None or mr.sender_user_id != auth.user.id:
            raise HTTPException(status_code=404, detail="Message request not found")
    payment = await create_credit_payment(
        session,
        settings,
        user=auth.user,
        message_request_id=body.message_request_id,
        pack=body.pack,
    )
    await send_credit_invoice(settings, user=auth.user, payment=payment)
    return {
        "ok": True,
        "payment_id": payment.id,
        "stars": payment.stars_amount,
        "pack": body.pack,
    }


@router.get("/messages/{request_id}/chat", response_model=ChatOut)
async def get_chat(
    request_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ChatOut:
    mr = await get_message_request(session, request_id, for_user=auth.user)
    if mr is None:
        raise HTTPException(status_code=404, detail="Not found")
    if mr.status not in {
        MessageRequestStatus.UNLOCKED.value,
        MessageRequestStatus.CHATTING.value,
    }:
        raise HTTPException(status_code=409, detail="Chat not unlocked")
    msgs = await list_chat_messages(session, mr)
    is_incoming = mr.profile.user_id == auth.user.id
    if is_incoming:
        counterpart = mr.sender_name
        link = _tg_link(mr.sender.telegram_username if mr.sender else None)
    else:
        counterpart = mr.profile.name if mr.profile else None
        uname = (
            (mr.profile.telegram_username if mr.profile else None)
            or (mr.profile.user.telegram_username if mr.profile and mr.profile.user else None)
        )
        link = _tg_link(uname)
    return ChatOut(
        request_id=mr.id,
        status=mr.status,
        messages=[
            ChatMessageOut(
                id=m.id,
                sender_user_id=m.sender_user_id,
                text=m.text,
                text_translated=m.text_translated,
                created_at=m.created_at,
                is_mine=m.sender_user_id == auth.user.id,
            )
            for m in msgs
        ],
        counterpart_name=counterpart,
        counterpart_telegram_link=link,
        can_send=True,
    )


@router.post("/messages/{request_id}/chat", response_model=ChatMessageOut)
async def post_chat(
    request_id: int,
    body: ChatSendIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ChatMessageOut:
    mr = await get_message_request(session, request_id, for_user=auth.user)
    if mr is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        msg = await send_chat_message(
            session, settings, mr=mr, actor=auth.user, text=body.text
        )
    except MessageServiceError as exc:
        _raise_service(exc)
    return ChatMessageOut(
        id=msg.id,
        sender_user_id=msg.sender_user_id,
        text=msg.text,
        text_translated=msg.text_translated,
        created_at=msg.created_at,
        is_mine=True,
    )


@router.get("/me/referral", response_model=ReferralOut)
async def get_referral(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ReferralOut:
    return await _referral_out(session, settings, auth.user)


async def _referral_out(session: AsyncSession, settings: Settings, user: User) -> ReferralOut:
    code = ensure_referral_code(user)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return ReferralOut(
        code=code,
        link=await referral_link(settings, code),
        referred_by_user_id=user.referred_by_user_id,
        invited_count=await count_invited(session, user),
        bonus_credits=max(0, settings.referral_bonus_credits),
    )


class ClaimReferralIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)


@router.post("/me/referral/claim", response_model=ReferralOut)
async def claim_referral(
    body: ClaimReferralIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ReferralOut:
    await claim_referral(session, settings, user=auth.user, code=body.code)
    return await _referral_out(session, settings, auth.user)
