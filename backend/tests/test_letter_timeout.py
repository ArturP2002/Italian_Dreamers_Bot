"""Pay-at-send letter timeout / late-reply reopen rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api.messages import _serialize_request
from app.config import Settings
from app.models import MessageRequest, MessageRequestStatus, Profile, ProfilePhoto, User


def _user(uid: int, *, credits: int = 0) -> User:
    u = User(telegram_id=uid * 100, telegram_username=f"u{uid}", message_credits=credits)
    u.id = uid
    return u


def _profile(owner: User, **kwargs) -> Profile:
    defaults = dict(
        name="Кристина",
        age=28,
        height_cm=168,
        country="Italia",
        city="Roma",
        profession="Designer",
        about="Ciao",
        desired_partner="Cerco",
        age_min=25,
        age_max=40,
        cover_question_id=1,
        cover_answer="Mare",
        personal_data_agreement=True,
        gender="female",
        telegram_username="kris",
        user_id=owner.id,
    )
    defaults.update(kwargs)
    profile = Profile(**defaults)
    profile.user = owner
    profile.photos = [ProfilePhoto(file_id="a", file_unique_id="a", position=0)]
    return profile


def test_reply_timeout_default_is_three_days() -> None:
    assert Settings().message_reply_timeout_days == 3


def test_outgoing_replied_hides_reply_until_unlock() -> None:
    sender = _user(11, credits=0)
    owner = _user(22, credits=1)
    profile = _profile(owner)
    mr = MessageRequest(
        text="hello there friend",
        status=MessageRequestStatus.REPLIED.value,
        created_at=datetime.now(timezone.utc),
        reply_text="Ciao!",
        reply_text_translated="Привет!",
        paid_at_send=True,
        credit_held=0,
    )
    mr.id = 9
    mr.sender_user_id = 11
    mr.profile_id = 1
    mr.sender = sender
    mr.profile = profile

    out = _serialize_request(mr, sender)
    assert out.direction == "outgoing"
    assert out.can_unlock is True
    assert out.can_chat is False
    assert out.reply_text is None
    assert out.reply_text_translated is None

    incoming = _serialize_request(mr, owner)
    assert incoming.direction == "incoming"
    assert incoming.reply_text == "Ciao!"
    assert incoming.can_reply is False


def test_expired_allows_recipient_reply() -> None:
    sender = _user(11)
    owner = _user(22)
    profile = _profile(owner)
    mr = MessageRequest(
        text="hello there friend",
        status=MessageRequestStatus.EXPIRED.value,
        created_at=datetime.now(timezone.utc) - timedelta(days=4),
        paid_at_send=True,
        credit_held=0,
        refunded_at=datetime.now(timezone.utc),
    )
    mr.id = 10
    mr.sender_user_id = 11
    mr.profile_id = 1
    mr.sender = sender
    mr.profile = profile

    incoming = _serialize_request(mr, owner)
    assert incoming.can_reply is True
    assert incoming.can_reject is False
    assert incoming.can_unlock is False

    outgoing = _serialize_request(mr, sender)
    assert outgoing.can_unlock is False
    assert outgoing.can_chat is False


def test_cutoff_for_timeout() -> None:
    days = Settings().message_reply_timeout_days
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    assert now - timedelta(days=days) <= now - timedelta(days=days)
    assert now - timedelta(days=days - 1) > now - timedelta(days=days)
