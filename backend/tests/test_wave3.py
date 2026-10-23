"""Wave 3: likes payloads, catalog top cursor, comment AI, weekly report window."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.catalog import decode_catalog_cursor, encode_catalog_cursor, encode_cursor
from app.services.comments_ai import parse_classifier_reply
from app.services.entitlements import extend_datetime, is_top_now
from app.services.payments import (
    make_sub_payload,
    make_top_payload,
    parse_any_payment_payload,
    parse_sub_payload,
    parse_top_payload,
)
from app.services.weekly_report import REPORT_HOUR, report_window
from types import SimpleNamespace


ROME = ZoneInfo("Europe/Rome")


def test_sub_and_top_payloads() -> None:
    assert parse_sub_payload(make_sub_payload(9)) == 9
    assert parse_top_payload(make_top_payload(3, 7)) == (3, 7)
    assert parse_any_payment_payload(make_sub_payload(1)) == "sub"
    assert parse_any_payment_payload(make_top_payload(2, 4)) == "top"
    assert parse_any_payment_payload("sub:x") is None


def test_catalog_cursor_keeps_top_tier() -> None:
    ts = datetime(2026, 10, 23, 12, tzinfo=ROME).astimezone()
    raw = encode_catalog_cursor(is_top=True, ts=ts, profile_id=44)
    is_top, decoded_ts, pid = decode_catalog_cursor(raw)  # type: ignore[misc]
    assert is_top == 1
    assert pid == 44
    assert abs(decoded_ts.timestamp() - ts.timestamp()) < 1
    old = encode_cursor(ts, 12)
    legacy = decode_catalog_cursor(old)
    assert legacy is not None
    assert legacy[0] == 0
    assert legacy[2] == 12


def test_classifier_json_and_keep_default() -> None:
    assert parse_classifier_reply('{"delete": true, "reason": "threat"}') == (True, "threat")
    assert parse_classifier_reply('{"delete": false, "reason": "flirt"}') == (False, "flirt")
    assert parse_classifier_reply("not json")[0] is False


def test_weekly_report_only_sunday_evening() -> None:
    saturday = datetime(2026, 10, 24, 20, 0, tzinfo=ROME)  # Saturday
    sunday_morning = datetime(2026, 10, 25, 10, 0, tzinfo=ROME)
    sunday_evening = datetime(2026, 10, 25, REPORT_HOUR, 5, tzinfo=ROME)
    assert report_window(saturday) is None
    assert report_window(sunday_morning) is None
    window = report_window(sunday_evening)
    assert window is not None
    start, end = window
    assert end.astimezone(ROME).hour == REPORT_HOUR
    assert (end - start).days == 6 or (end - start).total_seconds() >= 6 * 24 * 3600 - 3600


def test_top_until_extend() -> None:
    earlier = datetime(2026, 10, 1, tzinfo=ROME)
    later = datetime(2026, 11, 1, tzinfo=ROME)
    assert extend_datetime(None, later) == later
    assert extend_datetime(earlier, later) == later
    assert extend_datetime(later, earlier) == later
    profile = SimpleNamespace(top_until=later)
    assert is_top_now(profile, datetime(2026, 10, 15, tzinfo=ROME)) is True
    assert is_top_now(profile, datetime(2026, 12, 1, tzinfo=ROME)) is False
