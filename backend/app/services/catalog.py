"""Mini App catalog: queued + published profiles, cursor feed, already-written flag."""

from __future__ import annotations

import base64
from datetime import datetime, timezone

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    MessageRequest,
    MessageRequestStatus,
    Profile,
    ProfileStatus,
    User,
    VerificationStatus,
)
from app.services.entitlements import is_top_now

CATALOG_STATUSES = (ProfileStatus.QUEUED.value, ProfileStatus.PUBLISHED.value)
ACTIVE_LETTER_STATUSES = (
    MessageRequestStatus.PENDING.value,
    MessageRequestStatus.REPLIED.value,
    MessageRequestStatus.UNLOCKED.value,
    MessageRequestStatus.CHATTING.value,
)
PAGE_SIZE = 20


def _sort_ts():
    return func.coalesce(Profile.published_at, Profile.paid_at, Profile.created_at)


def encode_cursor(ts: datetime, profile_id: int) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    raw = f"{ts.timestamp()}:{profile_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int] | None:
    decoded = decode_catalog_cursor(cursor)
    if decoded is None:
        return None
    _is_top, ts, profile_id = decoded
    return ts, profile_id


def encode_catalog_cursor(*, is_top: bool, ts: datetime, profile_id: int) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    raw = f"{1 if is_top else 0}:{ts.timestamp()}:{profile_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_catalog_cursor(cursor: str) -> tuple[int, datetime, int] | None:
    if not cursor:
        return None
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        parts = raw.split(":")
        if len(parts) == 3:
            return int(parts[0]), datetime.fromtimestamp(float(parts[1]), tz=timezone.utc), int(parts[2])
        if len(parts) == 2:
            return 0, datetime.fromtimestamp(float(parts[0]), tz=timezone.utc), int(parts[1])
        return None
    except (ValueError, TypeError, OSError):
        return None


def _is_top_expr(now: datetime):
    return case(
        (and_(Profile.top_until.is_not(None), Profile.top_until > now), 1),
        else_=0,
    )


def photo_url(file_id: str | None) -> str | None:
    if not file_id:
        return None
    if file_id.startswith("local:"):
        return f"/media/profiles/{file_id.removeprefix('local:')}"
    return None


def default_catalog_gender(viewer: User, profile: Profile | None) -> str | None:
    source = (profile.gender if profile else None) or viewer.gender
    if source == "female":
        return "male"
    if source == "male":
        return "female"
    return None


async def written_profile_ids(
    session: AsyncSession,
    *,
    sender_id: int,
    profile_ids: list[int],
) -> dict[int, int]:
    if not profile_ids:
        return {}
    result = await session.execute(
        select(MessageRequest.profile_id, MessageRequest.id)
        .where(
            MessageRequest.sender_user_id == sender_id,
            MessageRequest.profile_id.in_(profile_ids),
            MessageRequest.status.in_(list(ACTIVE_LETTER_STATUSES)),
        )
        .order_by(MessageRequest.id.desc())
    )
    out: dict[int, int] = {}
    for profile_id, request_id in result.all():
        if profile_id is not None and profile_id not in out:
            out[int(profile_id)] = int(request_id)
    return out


async def list_catalog(
    session: AsyncSession,
    *,
    viewer: User,
    gender: str | None = None,
    age_min: int | None = None,
    age_max: int | None = None,
    verified: bool | None = None,
    cursor: str | None = None,
    limit: int = PAGE_SIZE,
) -> tuple[list[Profile], dict[int, int], str | None]:
    now = datetime.now(timezone.utc)
    stmt = (
        select(Profile)
        .where(
            Profile.status.in_(list(CATALOG_STATUSES)),
            Profile.user_id != viewer.id,
        )
        .options(selectinload(Profile.photos))
    )
    if gender in {"male", "female"}:
        stmt = stmt.where(Profile.gender == gender)
    if age_min is not None:
        stmt = stmt.where(Profile.age >= age_min)
    if age_max is not None:
        stmt = stmt.where(Profile.age <= age_max)
    if verified:
        stmt = stmt.where(Profile.verification_status == VerificationStatus.VERIFIED.value)

    sort_ts = _sort_ts()
    is_top = _is_top_expr(now)
    decoded = decode_catalog_cursor(cursor or "")
    if decoded:
        last_top, ts, pid = decoded
        stmt = stmt.where(
            or_(
                is_top < last_top,
                and_(
                    is_top == last_top,
                    or_(sort_ts < ts, and_(sort_ts == ts, Profile.id < pid)),
                ),
            )
        )

    stmt = stmt.order_by(is_top.desc(), sort_ts.desc(), Profile.id.desc()).limit(
        min(max(limit, 1), 50) + 1
    )
    profiles = list((await session.execute(stmt)).scalars().all())
    has_more = len(profiles) > limit
    profiles = profiles[:limit]
    written = await written_profile_ids(
        session, sender_id=viewer.id, profile_ids=[p.id for p in profiles]
    )
    next_cursor = None
    if has_more and profiles:
        last = profiles[-1]
        stamp = last.published_at or last.paid_at or last.created_at
        next_cursor = encode_catalog_cursor(
            is_top=is_top_now(last, now), ts=stamp, profile_id=last.id
        )
    return profiles, written, next_cursor


async def get_catalog_profile(session: AsyncSession, profile_id: int) -> Profile | None:
    result = await session.execute(
        select(Profile)
        .where(Profile.id == profile_id, Profile.status.in_(list(CATALOG_STATUSES)))
        .options(selectinload(Profile.photos), selectinload(Profile.user))
    )
    return result.scalar_one_or_none()


def card_photos(profile: Profile, *, limit: int = 4) -> list[str]:
    photos = sorted(profile.photos or [], key=lambda p: p.position)
    urls: list[str] = []
    for photo in photos[:limit]:
        url = photo_url(photo.file_id)
        if url:
            urls.append(url)
    return urls
