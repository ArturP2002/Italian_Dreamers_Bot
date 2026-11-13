"""Mini App catalog: queued + published profiles, cursor feed, already-written flag."""

from __future__ import annotations

import base64
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    MessageRequest,
    MessageRequestStatus,
    Profile,
    ProfileStatus,
    Subscription,
    SubscriptionStatus,
    User,
    VerificationStatus,
)
from app.services.entitlements import CATALOG_NEW_TTL, is_new_in_catalog, is_top_now, utcnow

CATALOG_STATUSES = (ProfileStatus.QUEUED.value, ProfileStatus.PUBLISHED.value)
ACTIVE_LETTER_STATUSES = (
    MessageRequestStatus.PENDING.value,
    MessageRequestStatus.REPLIED.value,
    MessageRequestStatus.UNLOCKED.value,
    MessageRequestStatus.CHATTING.value,
    MessageRequestStatus.EXPIRED.value,
)
PAGE_SIZE = 20
ROME = ZoneInfo("Europe/Rome")


def _activity_ts(profile: Profile) -> datetime:
    user = getattr(profile, "user", None)
    candidates = [
        getattr(user, "last_seen_at", None) if user else None,
        profile.published_at,
        profile.paid_at,
        profile.created_at,
    ]
    stamps = []
    for stamp in candidates:
        if stamp is None:
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        stamps.append(stamp)
    return max(stamps) if stamps else datetime(1970, 1, 1, tzinfo=timezone.utc)


def encode_cursor(ts: datetime, profile_id: int) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    raw = f"{ts.timestamp()}:{profile_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int] | None:
    decoded = decode_catalog_cursor(cursor)
    if decoded is None:
        return None
    _bucket, ts, profile_id = decoded
    return ts, profile_id


def encode_catalog_cursor(*, is_top: bool, ts: datetime, profile_id: int) -> str:
    """Legacy helper kept for tests; prefer encode_feed_cursor."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    raw = f"{1 if is_top else 0}:{ts.timestamp()}:{profile_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def encode_feed_cursor(*, phase: str, featured_offset: int = 0, ts: datetime | None = None, profile_id: int = 0) -> str:
    if phase == "f":
        raw = f"f:{featured_offset}"
    else:
        assert ts is not None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        raw = f"r:{ts.timestamp()}:{profile_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_catalog_cursor(cursor: str) -> tuple[int, datetime, int] | None:
    """Legacy tuple (is_top_flag, ts, id) for older callers/tests."""
    if not cursor:
        return None
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        parts = raw.split(":")
        if len(parts) == 3 and parts[0] in {"0", "1"}:
            return int(parts[0]), datetime.fromtimestamp(float(parts[1]), tz=timezone.utc), int(parts[2])
        if len(parts) == 2:
            return 0, datetime.fromtimestamp(float(parts[0]), tz=timezone.utc), int(parts[1])
        return None
    except (ValueError, TypeError, OSError):
        return None


def decode_feed_cursor(
    cursor: str,
) -> tuple[str, int, datetime | None, int] | None:
    """phase 'f'|'r', featured_offset, rest_ts, rest_id."""
    if not cursor:
        return None
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        if raw.startswith("f:"):
            return "f", int(raw.split(":", 1)[1]), None, 0
        if raw.startswith("r:"):
            _, ts_s, pid_s = raw.split(":", 2)
            return "r", 0, datetime.fromtimestamp(float(ts_s), tz=timezone.utc), int(pid_s)
        # Legacy cursors: treat as start of rest after that point
        parts = raw.split(":")
        if len(parts) == 3:
            return "r", 0, datetime.fromtimestamp(float(parts[1]), tz=timezone.utc), int(parts[2])
        if len(parts) == 2:
            return "r", 0, datetime.fromtimestamp(float(parts[0]), tz=timezone.utc), int(parts[1])
        return None
    except (ValueError, TypeError, OSError):
        return None


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


def _daily_shuffle(items: list[Profile], *, day_key: str) -> list[Profile]:
    bag = list(items)
    random.Random(day_key).shuffle(bag)
    return bag


def _interleave(tops: list[Profile], news: list[Profile]) -> list[Profile]:
    """↑ · NEW · ↑ · NEW… then leftovers of the longer list."""
    out: list[Profile] = []
    i = j = 0
    while i < len(tops) or j < len(news):
        if i < len(tops):
            out.append(tops[i])
            i += 1
        if j < len(news):
            out.append(news[j])
            j += 1
    return out


def _active_plus_user_ids_subq():
    """Users with Dreamers Plus still valid (active or canceled-until-expiry)."""
    now = utcnow()
    return (
        select(Subscription.user_id)
        .where(
            Subscription.expires_at > now,
            Subscription.status.in_(
                [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.CANCELED.value]
            ),
        )
        .distinct()
    )


def _base_filters(
    *,
    viewer: User,
    gender: str | None,
    age_min: int | None,
    age_max: int | None,
    verified: bool | None,
):
    conds = [
        Profile.status.in_(list(CATALOG_STATUSES)),
        Profile.user_id != viewer.id,
        # Without Plus the profile is hidden from Participants.
        Profile.user_id.in_(_active_plus_user_ids_subq()),
    ]
    if gender in {"male", "female"}:
        conds.append(Profile.gender == gender)
    if age_min is not None:
        conds.append(Profile.age >= age_min)
    if age_max is not None:
        conds.append(Profile.age <= age_max)
    if verified:
        conds.append(Profile.verification_status == VerificationStatus.VERIFIED.value)
    return conds


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
    day_key = now.astimezone(ROME).date().isoformat()
    page = min(max(limit, 1), 50)
    filters = _base_filters(
        viewer=viewer, gender=gender, age_min=age_min, age_max=age_max, verified=verified
    )

    featured_stmt = (
        select(Profile)
        .where(
            *filters,
            or_(
                and_(Profile.top_until.is_not(None), Profile.top_until > now),
                and_(
                    Profile.paid_at.is_not(None),
                    Profile.paid_at >= now - CATALOG_NEW_TTL,
                ),
                and_(
                    Profile.paid_at.is_(None),
                    Profile.approved_at.is_not(None),
                    Profile.approved_at >= now - CATALOG_NEW_TTL,
                ),
            ),
        )
        .options(selectinload(Profile.photos), selectinload(Profile.user))
    )
    featured_rows = list((await session.execute(featured_stmt)).scalars().unique().all())
    tops = [p for p in featured_rows if is_top_now(p, now)]
    news = [p for p in featured_rows if is_new_in_catalog(p, now)]
    news.sort(key=lambda p: p.paid_at or p.approved_at or p.created_at, reverse=True)
    featured = _interleave(_daily_shuffle(tops, day_key=f"top:{day_key}"), news)
    featured_ids = {p.id for p in featured}

    parsed = decode_feed_cursor(cursor or "")
    phase = "f"
    featured_offset = 0
    rest_ts: datetime | None = None
    rest_id = 0
    if parsed:
        phase, featured_offset, rest_ts, rest_id = parsed

    page_items: list[Profile] = []
    next_cursor: str | None = None

    if phase == "f":
        take = featured[featured_offset : featured_offset + page]
        page_items.extend(take)
        featured_offset += len(take)
        if featured_offset < len(featured):
            next_cursor = encode_feed_cursor(phase="f", featured_offset=featured_offset)
        elif len(page_items) == page:
            next_cursor = encode_feed_cursor(phase="r", ts=now, profile_id=0)

    need = page - len(page_items)
    if need > 0 and (phase == "r" or (phase == "f" and featured_offset >= len(featured) and next_cursor is None)):
        rest_stmt = (
            select(Profile)
            .join(User, User.id == Profile.user_id)
            .where(*filters)
            .options(selectinload(Profile.photos), selectinload(Profile.user))
        )
        if featured_ids:
            rest_stmt = rest_stmt.where(Profile.id.notin_(list(featured_ids)))
        rest_rows = list((await session.execute(rest_stmt)).scalars().unique().all())
        rest_rows.sort(key=lambda p: (_activity_ts(p), p.id), reverse=True)

        start = 0
        if phase == "r" and rest_ts is not None and rest_id:
            start = len(rest_rows)
            for idx, row in enumerate(rest_rows):
                stamp = _activity_ts(row)
                if stamp < rest_ts or (stamp == rest_ts and row.id < rest_id):
                    start = idx
                    break
                if stamp == rest_ts and row.id == rest_id:
                    start = idx + 1
                    break

        chunk = rest_rows[start : start + need]
        page_items.extend(chunk)
        if start + need < len(rest_rows) and chunk:
            last = chunk[-1]
            next_cursor = encode_feed_cursor(phase="r", ts=_activity_ts(last), profile_id=last.id)
        else:
            next_cursor = None

    written = await written_profile_ids(
        session, sender_id=viewer.id, profile_ids=[p.id for p in page_items]
    )
    return page_items, written, next_cursor


async def get_catalog_profile(session: AsyncSession, profile_id: int) -> Profile | None:
    result = await session.execute(
        select(Profile)
        .where(Profile.id == profile_id, Profile.status.in_(list(CATALOG_STATUSES)))
        .options(selectinload(Profile.photos), selectinload(Profile.user))
    )
    return result.scalar_one_or_none()


def localized_catalog_fields(profile: Profile, viewer_lang: str) -> dict[str, str]:
    """Return catalog text in the viewer's language when a cached translation exists."""
    from app.services.channel import source_language_for_profile

    lang = viewer_lang if viewer_lang in {"ru", "it"} else "ru"
    source = source_language_for_profile(profile)
    use_tr = (
        lang != source
        and profile.translated_language == lang
        and bool(profile.about_translated or profile.desired_partner_translated)
    )

    def pick(original: str | None, translated: str | None) -> str:
        if use_tr and translated:
            return translated
        return original or ""

    return {
        "name": pick(profile.name, profile.name_translated),
        "city": pick(profile.city, profile.city_translated),
        "country": pick(profile.country, profile.country_translated),
        "profession": pick(profile.profession, profile.profession_translated),
        "about": pick(profile.about, profile.about_translated),
        "desired_partner": pick(profile.desired_partner, profile.desired_partner_translated),
        "hobbies": profile.hobbies or "",
    }


def card_photos(profile: Profile, *, limit: int = 4) -> list[str]:
    photos = sorted(profile.photos or [], key=lambda p: p.position)
    urls: list[str] = []
    for photo in photos[:limit]:
        url = photo_url(photo.file_id)
        if url:
            urls.append(url)
    return urls
