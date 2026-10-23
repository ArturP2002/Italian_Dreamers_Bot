"""Wave 1: contacts, payments layer, username, publication cache, unpaid, limits."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.api.messages import _serialize_request, _tg_link
from app.models import MessageRequest, MessageRequestStatus, Profile, ProfilePhoto, User
from app.services.payments import (
    _stars_fields,
    make_ad_payload,
    make_credit_payload,
    make_pack_payload,
    make_publish_payload,
    parse_any_payment_payload,
)
from app.services.profiles import validate_for_submit
from app.services.publication_cache import cached_forward_action, remember_publication, reset_cache
from app.services.unpaid import DELETE_AFTER_DAYS, _anchor
from app.services.username_nudge import HOWTO_DIR, howto_paths, normalize_username


def _profile(**kwargs) -> Profile:
    defaults = dict(
        name="Anna",
        age=28,
        height_cm=168,
        country="Italia",
        city="Milano",
        profession="Designer",
        about="Ciao, vivo a Milano.",
        desired_partner="Cerco una relazione seria.",
        age_min=25,
        age_max=40,
        cover_question_id=1,
        cover_answer="Amo il mare",
        personal_data_agreement=True,
        gender="female",
        telegram_username=None,
    )
    defaults.update(kwargs)
    profile = Profile(**defaults)
    profile.photos = [
        ProfilePhoto(file_id="a", file_unique_id="a", position=0),
        ProfilePhoto(file_id="b", file_unique_id="b", position=1),
        ProfilePhoto(file_id="c", file_unique_id="c", position=2),
    ]
    return profile


def test_username_not_required_to_submit() -> None:
    errors = validate_for_submit(_profile(telegram_username=None))
    assert "telegram_username" not in errors
    assert errors == []


def test_submit_still_requires_core_fields() -> None:
    errors = validate_for_submit(_profile(name="", personal_data_agreement=False))
    assert "name" in errors
    assert "personal_data_agreement" in errors


def test_normalize_username() -> None:
    assert normalize_username(None) is None
    assert normalize_username("  ") is None
    assert normalize_username("@Anna_Milano") == "Anna_Milano"
    assert normalize_username("anna") == "anna"


def test_howto_images_exist_for_platforms() -> None:
    assert HOWTO_DIR.is_dir()
    ios = howto_paths("ios", "ru")
    android = howto_paths("android_x", "it")
    both = howto_paths("tdesktop", "ru")
    assert len(ios) == 1 and ios[0].name == "iphone_ru.jpg"
    assert len(android) == 1 and android[0].name == "android_it.jpg"
    assert {p.name for p in both} == {"iphone_ru.jpg", "android_ru.jpg"}
    assert all(p.is_file() for p in [*ios, *android, *both])


def test_stars_payment_fields_are_provider_agnostic() -> None:
    fields = _stars_fields(1000)
    assert fields["provider"] == "stars"
    assert fields["currency"] == "XTR"
    assert fields["amount"] == 1000
    assert fields["stars_amount"] == 1000


def test_payment_payloads_roundtrip() -> None:
    assert parse_any_payment_payload(make_publish_payload(1, 2)) == "publish"
    assert parse_any_payment_payload(make_credit_payload(3, 4)) == "credit"
    assert parse_any_payment_payload(make_pack_payload(5, None)) == "pack"
    assert parse_any_payment_payload(make_ad_payload(6, 7)) == "ad"
    assert parse_any_payment_payload("nope") is None


def test_contacts_hidden_until_chat_unlocks() -> None:
    sender = User(telegram_id=11, telegram_username="bob", message_credits=0)
    sender.id = 11
    owner = User(telegram_id=22, telegram_username="ann", message_credits=1)
    owner.id = 22
    owner.message_credits = 1
    profile = _profile(telegram_username="ann")
    profile.user_id = 22
    profile.user = owner
    mr = MessageRequest(
        text="hello there friend",
        status=MessageRequestStatus.PENDING.value,
        created_at=datetime.now(timezone.utc),
    )
    mr.id = 9
    mr.profile = profile
    mr.sender = sender
    mr.sender_user_id = 11
    mr.profile_id = 1

    pending = _serialize_request(mr, owner)
    assert pending.can_chat is False
    assert pending.counterpart_username is None
    assert pending.counterpart_telegram_link is None

    mr.status = MessageRequestStatus.CHATTING.value
    open_chat = _serialize_request(mr, owner)
    assert open_chat.can_chat is True
    assert open_chat.counterpart_username == "bob"
    assert open_chat.counterpart_telegram_link == "https://t.me/bob"


def test_tg_link_empty_without_username() -> None:
    assert _tg_link(None) is None
    assert _tg_link("  ") is None
    assert _tg_link("@x") == "https://t.me/x"


def test_publication_cache_keeps_splash_deletes_album() -> None:
    reset_cache()
    profile = SimpleNamespace(
        splash_message_id=10,
        channel_post_message_ids=[10, 11, 12],
    )
    remember_publication(profile)  # type: ignore[arg-type]
    assert cached_forward_action(10) is False
    assert cached_forward_action(11) is True
    assert cached_forward_action(12) is True
    assert cached_forward_action(999) is None
    reset_cache()


def test_unpaid_anchor_and_delete_window() -> None:
    profile = _profile()
    profile.approved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert _anchor(profile) == profile.approved_at
    assert DELETE_AFTER_DAYS == 30
    assert profile.approved_at + timedelta(days=DELETE_AFTER_DAYS) == datetime(
        2026, 1, 31, tzinfo=timezone.utc
    )
