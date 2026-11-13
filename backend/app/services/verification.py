"""Profile selfie verification with optional Vision face-match auto-decision."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import Profile, ProfilePhoto, User, VerificationStatus
from app.services.notify import notify_verification_result
from app.services.vision import compare_selfie_to_profile_photos

VERIFY_MEDIA = Path(__file__).resolve().parents[2] / "media" / "verify"
VERIFY_MEDIA.mkdir(parents=True, exist_ok=True)
MEDIA_PROFILES = Path(__file__).resolve().parents[2] / "media" / "profiles"


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


def _guess_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


def load_profile_photo_bytes(photos: list[ProfilePhoto], *, limit: int = 3) -> list[tuple[bytes, str]]:
    out: list[tuple[bytes, str]] = []
    for photo in sorted(photos, key=lambda p: p.position)[:limit]:
        fid = photo.file_id or ""
        if not fid.startswith("local:"):
            continue
        path = MEDIA_PROFILES / fid.removeprefix("local:")
        if not path.exists():
            continue
        try:
            out.append((path.read_bytes(), _guess_mime(path)))
        except OSError:
            continue
    return out


async def submit_selfie(
    session: AsyncSession,
    settings: Settings,
    profile: Profile,
    file_id: str,
    *,
    selfie_bytes: bytes,
    selfie_mime: str,
) -> Profile:
    if profile.status not in {"queued", "published", "awaiting_payment"}:
        raise VerificationError("too_early", "Publish the profile first")
    if profile.verification_status == VerificationStatus.VERIFIED.value:
        raise VerificationError("already", "Already verified")

    # Ensure photos are loaded for face match.
    if not profile.photos:
        result = await session.execute(
            select(Profile)
            .where(Profile.id == profile.id)
            .options(selectinload(Profile.photos), selectinload(Profile.user))
        )
        profile = result.scalar_one()

    profile_photos = load_profile_photo_bytes(list(profile.photos or []))
    match = await compare_selfie_to_profile_photos(
        selfie_bytes,
        selfie_mime=selfie_mime,
        profile_photos=profile_photos,
        api_key=settings.translation_api_key,
        model=settings.openai_vision_model,
    )

    profile.verification_photo_file_id = file_id
    profile.verification_auto_decision = match.decision
    profile.verification_auto_score = match.score
    profile.verification_auto_reason = match.reason[:500]

    user = profile.user
    if user is None:
        user_result = await session.execute(select(User).where(User.id == profile.user_id))
        user = user_result.scalar_one()

    if match.decision == "pass":
        profile.verification_status = VerificationStatus.VERIFIED.value
        profile.verified_at = datetime.now(timezone.utc)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        await notify_verification_result(settings, user=user, profile=profile, approved=True)
        return profile

    if match.decision == "fail":
        profile.verification_status = VerificationStatus.REJECTED.value
        profile.verified_at = None
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        await notify_verification_result(
            settings,
            user=user,
            profile=profile,
            approved=False,
            feedback=match.reason,
        )
        return profile

    # Grey zone / API issues → admin queue.
    profile.verification_status = VerificationStatus.PENDING.value
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
