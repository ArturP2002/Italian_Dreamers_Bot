"""Guest catalog: 15 unseen profiles per Rome day, then blur paywall."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import CatalogProfileView, Profile, ProfileStatus, User, WaitingTeaserPhoto
from app.services.catalog import CATALOG_STATUSES, _base_filters, card_photos
from app.services.registration import profile_is_registered

ROME = ZoneInfo("Europe/Rome")
GUEST_DAILY_LIMIT = 15


def rome_today() -> date:
    return datetime.now(timezone.utc).astimezone(ROME).date()


def floor_profile_count(n: int) -> int:
    """Round down for marketing copy: 3120 → 3000, 480 → 0→ keep small as-is."""
    if n < 500:
        return n
    return (n // 500) * 500


async def live_catalog_count(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count()).select_from(Profile).where(Profile.status.in_(list(CATALOG_STATUSES)))
    )
    return floor_profile_count(int(result.scalar_one()))


async def new_today_count(session: AsyncSession) -> int:
    """Profiles that entered the catalog since Rome midnight (with active Plus)."""
    from datetime import datetime, time, timezone

    from app.services.catalog import _active_plus_user_ids_subq

    day_start = datetime.combine(rome_today(), time.min, tzinfo=ROME).astimezone(timezone.utc)
    entered = func.coalesce(Profile.paid_at, Profile.approved_at, Profile.published_at)
    result = await session.execute(
        select(func.count())
        .select_from(Profile)
        .where(
            Profile.status.in_(list(CATALOG_STATUSES)),
            Profile.user_id.in_(_active_plus_user_ids_subq()),
            entered.is_not(None),
            entered >= day_start,
        )
    )
    return int(result.scalar_one())


async def guest_seen_ids(session: AsyncSession, user_id: int, day: date) -> set[int]:
    result = await session.execute(
        select(CatalogProfileView.profile_id).where(
            CatalogProfileView.user_id == user_id,
            CatalogProfileView.view_date == day,
        )
    )
    return {int(x) for x in result.scalars().all()}


async def record_guest_views(session: AsyncSession, user_id: int, profile_ids: list[int], day: date) -> None:
    existing = await guest_seen_ids(session, user_id, day)
    for pid in profile_ids:
        if pid in existing:
            continue
        session.add(CatalogProfileView(user_id=user_id, profile_id=pid, view_date=day))
        existing.add(pid)
    await session.commit()


async def list_guest_catalog(
    session: AsyncSession,
    *,
    viewer: User,
    gender: str | None,
    limit: int = 30,
) -> tuple[list[Profile], int, int]:
    """Returns (profiles for page, clear_count_today, free_remaining)."""
    day = rome_today()
    seen = await guest_seen_ids(session, viewer.id, day)
    clear_left = max(0, GUEST_DAILY_LIMIT - len(seen))

    filters = _base_filters(viewer=viewer, gender=gender, age_min=None, age_max=None, verified=False)
    stmt = (
        select(Profile)
        .where(*filters)
        .options(selectinload(Profile.photos), selectinload(Profile.user))
        .order_by(Profile.paid_at.desc().nullslast(), Profile.id.desc())
        .limit(max(limit, GUEST_DAILY_LIMIT + 12))
    )
    rows = list((await session.execute(stmt)).scalars().unique().all())

    unseen = [p for p in rows if p.id not in seen]
    already = [p for p in rows if p.id in seen]
    # Fresh first, then previously seen today, then extras for blur filler.
    ordered = unseen + already
    page = ordered[:limit]
    to_record = [p.id for p in page if p.id not in seen][:clear_left]
    if to_record:
        await record_guest_views(session, viewer.id, to_record, day)
        seen |= set(to_record)
    return page, len(seen), max(0, GUEST_DAILY_LIMIT - len(seen))


async def waiting_teaser_urls(session: AsyncSession, audience_gender: str | None) -> list[str]:
    gender = audience_gender if audience_gender in {"male", "female"} else "female"
    # Audience male → show women teasers (opposite).
    show = "female" if gender == "male" else "male"
    result = await session.execute(
        select(WaitingTeaserPhoto)
        .where(WaitingTeaserPhoto.audience_gender == show)
        .order_by(WaitingTeaserPhoto.position.asc())
        .limit(6)
    )
    urls: list[str] = []
    for row in result.scalars().all():
        fid = row.file_id or ""
        if fid.startswith("local:"):
            urls.append(f"/media/teasers/{fid.removeprefix('local:')}")
        elif fid.startswith("/"):
            urls.append(fid)
    if urls:
        return urls
    # Fallback: latest catalog photos of opposite gender.
    stmt = (
        select(Profile)
        .where(Profile.status.in_(list(CATALOG_STATUSES)), Profile.gender == show)
        .options(selectinload(Profile.photos))
        .order_by(Profile.paid_at.desc().nullslast())
        .limit(6)
    )
    profiles = list((await session.execute(stmt)).scalars().unique().all())
    out: list[str] = []
    for p in profiles:
        photos = card_photos(p)
        if photos:
            out.append(photos[0])
    return out[:6]
