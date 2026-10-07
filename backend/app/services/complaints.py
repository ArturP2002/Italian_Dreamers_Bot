"""User complaints about letters / profiles."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import Complaint, ComplaintStatus, MessageRequest, Profile, User
from app.services.telegram_api import send_message


class ComplaintServiceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def create_complaint(
    session: AsyncSession,
    settings: Settings,
    *,
    reporter: User,
    reason: str,
    message_request_id: int | None = None,
    reported_user_id: int | None = None,
) -> Complaint:
    cleaned = (reason or "").strip()
    if len(cleaned) < 3 or len(cleaned) > 2000:
        raise ComplaintServiceError("reason_invalid", "Reason must be 3–2000 characters")

    resolved_reported = reported_user_id
    if message_request_id is not None:
        result = await session.execute(
            select(MessageRequest).where(MessageRequest.id == message_request_id)
        )
        mr = result.scalar_one_or_none()
        if mr is None:
            raise ComplaintServiceError("not_found", "Message request not found")
        profile_result = await session.execute(select(Profile).where(Profile.id == mr.profile_id))
        profile = profile_result.scalar_one()
        if reporter.id not in {mr.sender_user_id, profile.user_id}:
            raise ComplaintServiceError("forbidden", "Not a participant")
        if reporter.id == mr.sender_user_id:
            resolved_reported = profile.user_id
        else:
            resolved_reported = mr.sender_user_id

    complaint = Complaint(
        reporter_user_id=reporter.id,
        reported_user_id=resolved_reported,
        message_request_id=message_request_id,
        reason=cleaned,
        status=ComplaintStatus.OPEN.value,
    )
    session.add(complaint)
    await session.commit()
    await session.refresh(complaint)

    for admin_id in settings.admin_ids:
        try:
            await send_message(
                settings,
                admin_id,
                (
                    f"⚠️ Жалоба #{complaint.id}\n"
                    f"От: tg {reporter.telegram_id}\n"
                    f"На user_id: {resolved_reported or '—'}\n"
                    f"MR: {message_request_id or '—'}\n"
                    f"{cleaned[:500]}"
                ),
                parse_mode=None,
            )
        except Exception:
            pass
    return complaint


async def list_complaints(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Complaint]:
    stmt = (
        select(Complaint)
        .options(selectinload(Complaint.reporter))
        .order_by(Complaint.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        stmt = stmt.where(Complaint.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_complaint(session: AsyncSession, complaint_id: int) -> Complaint | None:
    result = await session.execute(
        select(Complaint)
        .where(Complaint.id == complaint_id)
        .options(selectinload(Complaint.reporter))
    )
    return result.scalar_one_or_none()


async def resolve_complaint(
    session: AsyncSession,
    complaint: Complaint,
    *,
    status: str,
    admin_note: str | None = None,
) -> Complaint:
    allowed = {
        ComplaintStatus.REVIEWED.value,
        ComplaintStatus.RESOLVED.value,
        ComplaintStatus.DISMISSED.value,
    }
    if status not in allowed:
        raise ComplaintServiceError("bad_status", "Invalid complaint status")
    complaint.status = status
    complaint.admin_note = (admin_note or "").strip() or None
    if status in {
        ComplaintStatus.RESOLVED.value,
        ComplaintStatus.DISMISSED.value,
    }:
        complaint.resolved_at = datetime.now(timezone.utc)
    session.add(complaint)
    await session.commit()
    await session.refresh(complaint)
    return complaint
