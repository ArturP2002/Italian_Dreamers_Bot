"""Daily 5+5 publication slots (Rome). Leftover same-day slots go to the other gender."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import Profile, ProfileStatus, PublicationSlot

AD_COLLISION_HOUR = 10  # ads FIFO is 10:00 Rome; keep profile posts off that minute

DEFAULT_SLOT_TIMES = (
    "09:00",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
    "20:00",
)
SLOT_GENDERS = (
    "female",
    "male",
    "female",
    "male",
    "female",
    "male",
    "female",
    "male",
    "female",
    "male",
)
HORIZON_DAYS = 60


@dataclass(frozen=True)
class SlotChoice:
    slot_date: date
    slot_index: int
    time_local: str
    gender: str


def slot_times(settings: Settings | None = None) -> tuple[str, ...]:
    if settings is None:
        return DEFAULT_SLOT_TIMES
    raw = [part.strip() for part in settings.slot_times.split(",") if part.strip()]
    if len(raw) != 10:
        return DEFAULT_SLOT_TIMES
    return tuple(raw)


def slot_genders(settings: Settings | None = None) -> tuple[str, ...]:
    times = slot_times(settings)
    n = len(times)
    per = settings.slot_per_gender_per_day if settings else 5
    per = max(1, min(per, n // 2 if n >= 2 else 1))
    genders: list[str] = []
    female_left = per
    male_left = n - per
    # Interleave so leftover-of-the-day is spread, not a block at the end.
    for i in range(n):
        want_female = i % 2 == 0
        if want_female and female_left:
            genders.append("female")
            female_left -= 1
        elif male_left:
            genders.append("male")
            male_left -= 1
        else:
            genders.append("female")
            female_left -= 1
    return tuple(genders)


def parse_hhmm(value: str) -> tuple[int, int]:
    parts = (value or "09:00").split(":")
    return int(parts[0]), int(parts[1] if len(parts) > 1 else 0)


def slot_local_dt(slot_date: date, hhmm: str, tz: ZoneInfo) -> datetime:
    hour, minute = parse_hhmm(hhmm)
    return datetime(slot_date.year, slot_date.month, slot_date.day, hour, minute, tzinfo=tz)


def avoid_ad_collision(local_dt: datetime) -> datetime:
    if local_dt.hour == AD_COLLISION_HOUR and local_dt.minute == 0:
        return local_dt.replace(minute=15)
    return local_dt


def scheduled_utc(slot_date: date, hhmm: str, tz: ZoneInfo) -> datetime:
    return avoid_ad_collision(slot_local_dt(slot_date, hhmm, tz)).astimezone(timezone.utc)


def choose_open_slot(
    slots: list[PublicationSlot],
    *,
    gender: str | None,
    now_local: datetime,
) -> PublicationSlot | None:
    """Prefer same-gender free future slot; else leftover of that day; else later days."""
    want = gender if gender in {"male", "female"} else None
    by_day: dict[date, list[PublicationSlot]] = {}
    for slot in slots:
        by_day.setdefault(slot.slot_date, []).append(slot)
    tz = now_local.tzinfo or timezone.utc

    for day in sorted(by_day):
        group = sorted(by_day[day], key=lambda s: s.slot_index)
        free: list[PublicationSlot] = []
        for slot in group:
            if slot.profile_id is not None:
                continue
            local = slot_local_dt(slot.slot_date, slot.time_local, tz)  # type: ignore[arg-type]
            if local <= now_local:
                continue
            free.append(slot)
        if not free:
            continue
        if want is None:
            return free[0]
        same = [s for s in free if s.gender == want]
        if same:
            return same[0]
        return free[0]
    return None


async def ensure_slots_for_date(
    session: AsyncSession,
    day: date,
    settings: Settings,
) -> list[PublicationSlot]:
    result = await session.execute(
        select(PublicationSlot)
        .where(PublicationSlot.slot_date == day)
        .order_by(PublicationSlot.slot_index.asc())
    )
    existing = list(result.scalars().all())
    if existing:
        return existing
    times = slot_times(settings)
    genders = slot_genders(settings)
    created: list[PublicationSlot] = []
    for index, (hhmm, gender) in enumerate(zip(times, genders)):
        slot = PublicationSlot(
            slot_date=day,
            slot_index=index,
            time_local=hhmm,
            gender=gender,
        )
        session.add(slot)
        created.append(slot)
    await session.flush()
    return created


async def _slots_horizon(
    session: AsyncSession,
    settings: Settings,
    *,
    start: date,
    days: int = HORIZON_DAYS,
) -> list[PublicationSlot]:
    out: list[PublicationSlot] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        out.extend(await ensure_slots_for_date(session, day, settings))
    return out


async def vacate_profile_slots(session: AsyncSession, profile_id: int) -> None:
    result = await session.execute(
        select(PublicationSlot).where(PublicationSlot.profile_id == profile_id)
    )
    for slot in result.scalars():
        slot.profile_id = None
        session.add(slot)


async def assign_next_slot(
    session: AsyncSession,
    settings: Settings,
    profile: Profile,
) -> PublicationSlot | None:
    tz = ZoneInfo(settings.app_timezone)
    now_local = datetime.now(tz)
    await vacate_profile_slots(session, profile.id)
    slots = await _slots_horizon(session, settings, start=now_local.date())
    chosen = choose_open_slot(slots, gender=profile.gender, now_local=now_local)
    if chosen is None:
        return None
    chosen.profile_id = profile.id
    profile.scheduled_at = scheduled_utc(chosen.slot_date, chosen.time_local, tz)
    session.add(chosen)
    session.add(profile)
    await session.flush()
    return chosen


async def place_profile_at(
    session: AsyncSession,
    settings: Settings,
    profile: Profile,
    when: datetime,
) -> PublicationSlot | None:
    tz = ZoneInfo(settings.app_timezone)
    if when.tzinfo is None:
        when = when.replace(tzinfo=tz)
    local = when.astimezone(tz)
    day = local.date()
    slots = await ensure_slots_for_date(session, day, settings)
    hhmm = local.strftime("%H:%M")

    def _delta(slot: PublicationSlot) -> int:
        sh, sm = parse_hhmm(slot.time_local)
        th, tm = parse_hhmm(hhmm)
        return abs((sh * 60 + sm) - (th * 60 + tm))

    empty = [s for s in slots if s.profile_id in {None, profile.id}]
    pool = empty or slots
    target = min(pool, key=_delta)
    occupant_id = target.profile_id if target.profile_id not in {None, profile.id} else None
    await vacate_profile_slots(session, profile.id)
    if occupant_id:
        # Previous occupant keeps a slot: same-day leftover, else the next free day.
        other = await session.get(Profile, occupant_id)
        freed = [s for s in slots if s.profile_id is None and s.id != target.id]
        if other is not None and freed:
            alt = min(freed, key=_delta)
            alt.profile_id = other.id
            other.scheduled_at = scheduled_utc(alt.slot_date, alt.time_local, tz)
            session.add(alt)
            session.add(other)
        elif other is not None:
            other.scheduled_at = None
            session.add(other)
            await assign_next_slot(session, settings, other)
    target.profile_id = profile.id
    profile.scheduled_at = avoid_ad_collision(local).astimezone(timezone.utc)
    session.add(target)
    session.add(profile)
    await session.flush()
    return target


async def swap_slots(
    session: AsyncSession,
    settings: Settings,
    slot_a_id: int,
    slot_b_id: int,
) -> tuple[PublicationSlot, PublicationSlot]:
    tz = ZoneInfo(settings.app_timezone)
    slot_a = await session.get(PublicationSlot, slot_a_id)
    slot_b = await session.get(PublicationSlot, slot_b_id)
    if slot_a is None or slot_b is None:
        raise ValueError("Slot not found")
    pid_a, pid_b = slot_a.profile_id, slot_b.profile_id
    slot_a.profile_id, slot_b.profile_id = pid_b, pid_a
    session.add(slot_a)
    session.add(slot_b)
    for slot, pid in ((slot_a, slot_a.profile_id), (slot_b, slot_b.profile_id)):
        if pid is None:
            continue
        profile = await session.get(Profile, pid)
        if profile is None:
            continue
        profile.scheduled_at = scheduled_utc(slot.slot_date, slot.time_local, tz)
        session.add(profile)
    await session.flush()
    return slot_a, slot_b


async def occupy_slot(
    session: AsyncSession,
    settings: Settings,
    slot: PublicationSlot,
    profile: Profile,
) -> PublicationSlot:
    tz = ZoneInfo(settings.app_timezone)
    if slot.profile_id and slot.profile_id != profile.id:
        previous = await session.get(Profile, slot.profile_id)
        if previous is not None and previous.status == ProfileStatus.QUEUED.value:
            previous.scheduled_at = None
            session.add(previous)
        slot.profile_id = None
    await vacate_profile_slots(session, profile.id)
    slot.profile_id = profile.id
    profile.scheduled_at = scheduled_utc(slot.slot_date, slot.time_local, tz)
    session.add(slot)
    session.add(profile)
    await session.flush()
    return slot


async def list_day_slots(
    session: AsyncSession,
    settings: Settings,
    day: date,
) -> list[PublicationSlot]:
    slots = await ensure_slots_for_date(session, day, settings)
    result = await session.execute(
        select(PublicationSlot)
        .where(PublicationSlot.slot_date == day)
        .options(selectinload(PublicationSlot.profile).selectinload(Profile.photos))
        .order_by(PublicationSlot.slot_index.asc())
    )
    return list(result.scalars().all())


async def backfill_unscheduled_queued(session: AsyncSession, settings: Settings) -> int:
    result = await session.execute(
        select(Profile).where(
            Profile.status == ProfileStatus.QUEUED.value,
            Profile.scheduled_at.is_(None),
        )
    )
    profiles = list(result.scalars().all())
    n = 0
    for profile in profiles:
        if await assign_next_slot(session, settings, profile):
            n += 1
    return n
