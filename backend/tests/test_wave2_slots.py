"""Wave 2: 5+5 slots, leftover to the other gender, catalog cursor, no username leak."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.models import ProfileStatus
from app.services.catalog import CATALOG_STATUSES, decode_cursor, default_catalog_gender, encode_cursor
from app.services.slots import (
    DEFAULT_SLOT_TIMES,
    SLOT_GENDERS,
    avoid_ad_collision,
    choose_open_slot,
    slot_genders,
    slot_local_dt,
)


ROME = ZoneInfo("Europe/Rome")


def _slot(day: date, index: int, *, profile_id: int | None = None, gender: str | None = None):
    return SimpleNamespace(
        slot_date=day,
        slot_index=index,
        time_local=DEFAULT_SLOT_TIMES[index],
        gender=gender or SLOT_GENDERS[index],
        profile_id=profile_id,
    )


def test_five_plus_five_genders() -> None:
    genders = slot_genders()
    assert len(genders) == 10
    assert genders.count("female") == 5
    assert genders.count("male") == 5


def test_prefer_same_gender_then_leftover() -> None:
    day = date(2026, 10, 24)
    now = datetime(2026, 10, 24, 8, 0, tzinfo=ROME)
    occupied_female = [_slot(day, i, profile_id=1) for i, g in enumerate(SLOT_GENDERS) if g == "female"]
    empty_male = [_slot(day, i) for i, g in enumerate(SLOT_GENDERS) if g == "male"]
    slots = occupied_female + empty_male
    chosen = choose_open_slot(slots, gender="female", now_local=now)  # type: ignore[arg-type]
    assert chosen is not None
    assert chosen.gender == "male"


def test_skip_past_slots_today() -> None:
    day = date(2026, 10, 24)
    now = datetime(2026, 10, 24, 16, 30, tzinfo=ROME)
    slots = [_slot(day, i) for i in range(10)]
    chosen = choose_open_slot(slots, gender="female", now_local=now)  # type: ignore[arg-type]
    assert chosen is not None
    local = slot_local_dt(chosen.slot_date, chosen.time_local, ROME)
    assert local > now
    assert chosen.gender == "female"


def test_ad_collision_shifts_10am() -> None:
    dt = datetime(2026, 10, 24, 10, 0, tzinfo=ROME)
    shifted = avoid_ad_collision(dt)
    assert shifted.hour == 10 and shifted.minute == 15
    other = datetime(2026, 10, 24, 11, 0, tzinfo=ROME)
    assert avoid_ad_collision(other) == other


def test_catalog_cursor_roundtrip() -> None:
    ts = datetime(2026, 10, 23, 12, 0, tzinfo=ROME)
    cur = encode_cursor(ts, 42)
    decoded = decode_cursor(cur)
    assert decoded is not None
    got_ts, got_id = decoded
    assert got_id == 42
    assert abs(got_ts.timestamp() - ts.timestamp()) < 1


def test_catalog_and_letters_share_queued_published() -> None:
    assert set(CATALOG_STATUSES) == {
        ProfileStatus.QUEUED.value,
        ProfileStatus.PUBLISHED.value,
    }


def test_default_catalog_gender_is_opposite() -> None:
    user = SimpleNamespace(gender="male")
    profile = SimpleNamespace(gender="female")
    assert default_catalog_gender(user, None) == "female"  # type: ignore[arg-type]
    assert default_catalog_gender(user, profile) == "male"  # type: ignore[arg-type]
    assert default_catalog_gender(SimpleNamespace(gender=None), None) is None  # type: ignore[arg-type]
