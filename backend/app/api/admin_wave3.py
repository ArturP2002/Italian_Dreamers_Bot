"""Admin Wave 3: verification, legacy anketa, comment journal, weekly reports."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.config import Settings, get_settings
from app.database import get_session
from app.models import LegacyAnketa, Profile
from app.services.comments_ai import list_comments, mark_false_positive
from app.services.legacy import LegacyServiceError, create_legacy, invite_legacy, list_legacy, skip_legacy
from app.services.verification import decide_verification, list_pending, verification_photo_url
from app.services.weekly_report import list_reports

router = APIRouter()


class VerificationOut(BaseModel):
    id: int
    name: str
    age: int
    city: str
    status: str
    verification_status: str
    photo_url: str | None
    user_telegram_id: int | None
    username: str | None


class VerificationDecide(BaseModel):
    approved: bool
    feedback: str | None = Field(default=None, max_length=500)


class LegacyIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    gender: str | None = None
    city: str | None = None
    age: int | None = Field(default=None, ge=18, le=99)
    channel_message_id: int | None = None
    telegram_username: str | None = None
    notes: str | None = None


class LegacyOut(BaseModel):
    id: int
    name: str
    gender: str | None
    city: str | None
    age: int | None
    channel_message_id: int | None
    telegram_username: str | None
    notes: str | None
    status: str
    invite_token: str | None
    invited_at: datetime | None
    activated_user_id: int | None
    created_at: datetime


class CommentOut(BaseModel):
    id: int
    chat_id: int
    telegram_user_id: int
    telegram_message_id: int
    username: str | None
    text: str
    decision: str
    reason: str | None
    created_at: datetime


class ReportOut(BaseModel):
    id: int
    period_start: datetime
    period_end: datetime
    payload: dict
    sent_at: datetime | None


def _verify_out(profile: Profile) -> VerificationOut:
    user = profile.user
    return VerificationOut(
        id=profile.id,
        name=profile.name,
        age=profile.age,
        city=profile.city,
        status=profile.status,
        verification_status=profile.verification_status,
        photo_url=verification_photo_url(profile.verification_photo_file_id),
        user_telegram_id=user.telegram_id if user else None,
        username=(user.telegram_username if user else None) or profile.telegram_username,
    )


def _legacy_out(row: LegacyAnketa) -> LegacyOut:
    return LegacyOut(
        id=row.id,
        name=row.name,
        gender=row.gender,
        city=row.city,
        age=row.age,
        channel_message_id=row.channel_message_id,
        telegram_username=row.telegram_username,
        notes=row.notes,
        status=row.status,
        invite_token=row.invite_token,
        invited_at=row.invited_at,
        activated_user_id=row.activated_user_id,
        created_at=row.created_at,
    )


@router.get("/verifications", response_model=list[VerificationOut])
async def admin_verifications(
    _auth=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[VerificationOut]:
    return [_verify_out(p) for p in await list_pending(session)]


@router.post("/verifications/{profile_id}", response_model=VerificationOut)
async def admin_decide_verification(
    profile_id: int,
    body: VerificationDecide,
    _auth=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> VerificationOut:
    result = await session.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile = await decide_verification(
        session, settings, profile, approved=body.approved, feedback=body.feedback
    )
    return _verify_out(profile)


@router.get("/legacy", response_model=list[LegacyOut])
async def admin_legacy_list(
    status_filter: str | None = Query(default=None, alias="status"),
    _auth=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[LegacyOut]:
    return [_legacy_out(r) for r in await list_legacy(session, status=status_filter)]


@router.post("/legacy", response_model=LegacyOut)
async def admin_legacy_create(
    body: LegacyIn,
    _auth=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> LegacyOut:
    try:
        row = await create_legacy(session, **body.model_dump())
    except LegacyServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc
    return _legacy_out(row)


@router.post("/legacy/{anketa_id}/invite", response_model=LegacyOut)
async def admin_legacy_invite(
    anketa_id: int,
    _auth=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> LegacyOut:
    result = await session.execute(select(LegacyAnketa).where(LegacyAnketa.id == anketa_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    row = await invite_legacy(session, settings, row)
    return _legacy_out(row)


@router.post("/legacy/{anketa_id}/skip", response_model=LegacyOut)
async def admin_legacy_skip(
    anketa_id: int,
    _auth=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> LegacyOut:
    result = await session.execute(select(LegacyAnketa).where(LegacyAnketa.id == anketa_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _legacy_out(await skip_legacy(session, row))


@router.get("/comments", response_model=list[CommentOut])
async def admin_comments(
    decision: str | None = Query(default="delete"),
    _auth=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[CommentOut]:
    rows = await list_comments(session, decision=None if decision in {None, "", "all"} else decision)
    return [
        CommentOut(
            id=r.id,
            chat_id=r.chat_id,
            telegram_user_id=r.telegram_user_id,
            telegram_message_id=r.telegram_message_id,
            username=r.username,
            text=r.text,
            decision=r.decision,
            reason=r.reason,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/comments/{comment_id}/false-positive", response_model=CommentOut)
async def admin_comment_fp(
    comment_id: int,
    _auth=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> CommentOut:
    row = await mark_false_positive(session, comment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return CommentOut(
        id=row.id,
        chat_id=row.chat_id,
        telegram_user_id=row.telegram_user_id,
        telegram_message_id=row.telegram_message_id,
        username=row.username,
        text=row.text,
        decision=row.decision,
        reason=row.reason,
        created_at=row.created_at,
    )


@router.get("/reports", response_model=list[ReportOut])
async def admin_reports(
    _auth=Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ReportOut]:
    rows = await list_reports(session)
    return [
        ReportOut(
            id=r.id,
            period_start=r.period_start,
            period_end=r.period_end,
            payload=r.payload or {},
            sent_at=r.sent_at,
        )
        for r in rows
    ]
