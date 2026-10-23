"""Profile selfie verification."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import Profile, User, VerificationStatus
from app.services.notify import notify_verification_result

VERIFY_MEDIA = Path(__file__).resolve().parents[2] / "media" / "verify"
VERIFY_MEDIA.mkdir(parents=True, exist_ok=True)


class VerificationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def verification_photo_url(file_id: str | None) -> str | None:
    if not file_id:
        return None
    if file_id.startswith("local:"):
        return f"/media/verify/{file_id.removeprefix('local:')}"
    return None


async def submit_selfie(session: AsyncSession, profile: Profile, file_id: str) -> Profile:
    if profile.status not in {"queued", "published", "awaiting_payment"}:
        raise VerificationError("too_early", "Publish the profile first")
    if profile.verification_status == VerificationStatus.VERIFIED.value:
        raise VerificationError("already", "Already verified")
    profile.verification_status = VerificationStatus.PENDING.value
    profile.verification_photo_file_id = file_id
    profile.verified_at = None
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def list_pending(session: AsyncSession) -> list[Profile]:
    result = await session.execute(
        select(Profile)
        .where(Profile.verification_status == VerificationStatus.PENDING.value)
        .options(selectinload(Profile.user), selectinload(Profile.photos))
        .order_by(Profile.id.desc())
        .limit(100)
    )
    return list(result.scalars().all())


async def decide_verification(
    session: AsyncSession,
    settings: Settings,
    profile: Profile,
    *,
    approved: bool,
    feedback: str | None = None,
) -> Profile:
    user = profile.user
    if user is None:
        result = await session.execute(select(User).where(User.id == profile.user_id))
        user = result.scalar_one()
    if approved:
        profile.verification_status = VerificationStatus.VERIFIED.value
        profile.verified_at = datetime.now(timezone.utc)
    else:
        profile.verification_status = VerificationStatus.REJECTED.value
        profile.verified_at = None
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    await notify_verification_result(settings, user=user, profile=profile, approved=approved, feedback=feedback)
    return profile
