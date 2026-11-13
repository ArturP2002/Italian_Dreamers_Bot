"""Message requests: pay-at-send, 3-day reply window, unlock after late reply."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import (
    ChatMessage,
    CreditLedgerEntry,
    LedgerEntryType,
    MessageRequest,
    MessageRequestStatus,
    Profile,
    User,
)
from app.services.anti_contact import contains_contact_info
from app.services.catalog import CATALOG_STATUSES
from app.services.entitlements import has_unlimited
from app.services.notify import (
    notify_initiator_chat_opened,
    notify_initiator_pay_to_unlock,
    notify_letter_expired,
    notify_new_letter,
    notify_parties_unlocked,
    notify_recipient_rejected,
)


class MessageServiceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


ACTIVE_PAIR_STATUSES = (
    MessageRequestStatus.PENDING.value,
    MessageRequestStatus.REPLIED.value,
    MessageRequestStatus.UNLOCKED.value,
    MessageRequestStatus.CHATTING.value,
    MessageRequestStatus.EXPIRED.value,
)


def _lang(user: User | None, fallback: str = "ru") -> str:
    if user and user.language_code in {"ru", "it"}:
        return user.language_code
    return fallback


def _counterpart_lang(source: str) -> str:
    return "it" if source == "ru" else "ru"


async def get_published_profile(session: AsyncSession, profile_id: int) -> Profile | None:
    """Profile that can receive a letter: in the Mini App catalog (queued or published)."""
    result = await session.execute(
        select(Profile)
        .where(Profile.id == profile_id, Profile.status.in_(list(CATALOG_STATUSES)))
        .options(selectinload(Profile.user), selectinload(Profile.photos))
    )
    return result.scalar_one_or_none()


async def get_message_request(
    session: AsyncSession,
    request_id: int,
    *,
    for_user: User | None = None,
) -> MessageRequest | None:
    result = await session.execute(
        select(MessageRequest)
        .where(MessageRequest.id == request_id)
        .options(
            selectinload(MessageRequest.profile).selectinload(Profile.user),
            selectinload(MessageRequest.profile).selectinload(Profile.photos),
            selectinload(MessageRequest.sender),
            selectinload(MessageRequest.chat_messages),
        )
    )
    mr = result.scalar_one_or_none()
    if mr is None:
        return None
    if for_user is not None:
        owner_id = mr.profile.user_id if mr.profile else None
        if for_user.id not in {mr.sender_user_id, owner_id}:
            return None
    return mr


async def _assert_can_send(
    session: AsyncSession,
    settings: Settings,
    *,
    sender: User,
    profile: Profile,
) -> None:
    if sender.is_blocked:
        raise MessageServiceError("blocked", "User is blocked")
    now = datetime.now(timezone.utc)
    if profile.user_id == sender.id:
        raise MessageServiceError("self", "Cannot write to your own profile")

    pending_pair = await session.execute(
        select(func.count())
        .select_from(MessageRequest)
        .where(
            MessageRequest.profile_id == profile.id,
            MessageRequest.sender_user_id == sender.id,
            MessageRequest.status.in_(list(ACTIVE_PAIR_STATUSES)),
        )
    )
    if int(pending_pair.scalar_one()) > 0:
        raise MessageServiceError("duplicate", "Already have an active request to this profile")

    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    hour_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(MessageRequest)
                .where(
                    MessageRequest.sender_user_id == sender.id,
                    MessageRequest.created_at >= hour_ago,
                )
            )
        ).scalar_one()
    )
    day_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(MessageRequest)
                .where(
                    MessageRequest.sender_user_id == sender.id,
                    MessageRequest.created_at >= day_ago,
                )
            )
        ).scalar_one()
    )
    if hour_count >= settings.rate_contact_per_hour:
        raise MessageServiceError("rate_hour", "Hourly letter limit")
    if day_count >= settings.rate_contact_per_day:
        raise MessageServiceError("rate_day", "Daily letter limit")


async def _charge_send(
    session: AsyncSession,
    *,
    sender: User,
    mr: MessageRequest,
) -> None:
    """Plus-only: send allowed with active Plus OR remaining gift slots.

    Gifts are not spent on send — only when the recipient replies (unlock).
    Letters without a reply never consume a gift.
    """
    from app.services.registration import gifts_remaining

    unlimited = await has_unlimited(session, sender.id)
    if unlimited:
        mr.paid_at_send = True
        mr.credit_held = 0
        sender.first_message_free_used = True
        session.add(sender)
        return
    if gifts_remaining(sender) > 0:
        # Pending gift letter — no debit until reply opens the chat.
        mr.paid_at_send = False
        mr.credit_held = 0
        sender.first_message_free_used = True
        session.add(sender)
        return
    raise MessageServiceError("need_plus", "Dreamers Plus required to write")


async def refund_held_credit(
    session: AsyncSession,
    *,
    mr: MessageRequest,
    note: str = "letter_refund",
) -> bool:
    """Return held credit to the sender. Returns True if a credit was refunded."""
    if mr.credit_held < 1:
        return False
    sender = mr.sender
    if sender is None:
        result = await session.execute(select(User).where(User.id == mr.sender_user_id))
        sender = result.scalar_one_or_none()
    if sender is None:
        return False
    amount = mr.credit_held
    sender.message_credits += amount
    mr.credit_held = 0
    mr.refunded_at = datetime.now(timezone.utc)
    session.add(sender)
    session.add(mr)
    session.add(
        CreditLedgerEntry(
            user_id=sender.id,
            entry_type=LedgerEntryType.REFUND.value,
            delta=amount,
            balance_after=sender.message_credits,
            message_request_id=mr.id,
            note=note,
        )
    )
    return True


async def _seed_chat_from_letter(session: AsyncSession, mr: MessageRequest) -> None:
    existing = await session.execute(
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.message_request_id == mr.id)
    )
    if int(existing.scalar_one()) > 0:
        return
    session.add(
        ChatMessage(
            message_request_id=mr.id,
            sender_user_id=mr.sender_user_id,
            text=mr.text,
            text_translated=mr.text_translated,
        )
    )
    if mr.reply_text and mr.profile is not None:
        session.add(
            ChatMessage(
                message_request_id=mr.id,
                sender_user_id=mr.profile.user_id,
                text=mr.reply_text,
                text_translated=mr.reply_text_translated,
            )
        )


async def create_message_request(
    session: AsyncSession,
    settings: Settings,
    *,
    sender: User,
    profile: Profile,
    text: str,
    sender_name: str,
    sender_age: int,
    sender_photo_file_id: str | None,
    remember_identity: bool = True,
) -> MessageRequest:
    cleaned = (text or "").strip()
    if len(cleaned) < 10:
        raise MessageServiceError("text_short", "Message too short")
    if len(cleaned) > 1200:
        raise MessageServiceError("text_long", "Message too long")
    if contains_contact_info(cleaned):
        raise MessageServiceError("contact_forbidden", "Contact details are not allowed")
    name = (sender_name or "").strip()
    if not name or len(name) > 40:
        raise MessageServiceError("name_invalid", "Invalid sender name")
    if sender_age < 18 or sender_age > 99:
        raise MessageServiceError("age_invalid", "Invalid sender age")

    await _assert_can_send(session, settings, sender=sender, profile=profile)

    source_lang = _lang(sender)
    recipient = profile.user
    target_lang = _lang(recipient, _counterpart_lang(source_lang))
    translated = await translate_text_safe(
        cleaned,
        target_language=target_lang,
        source_language=source_lang,
        settings=settings,
    )

    if remember_identity:
        sender.stated_name = name
        sender.stated_age = sender_age
        if sender_photo_file_id:
            sender.stated_photo_file_id = sender_photo_file_id
        session.add(sender)
        from app.services.profiles import seed_mini_anketa_from_letter

        await seed_mini_anketa_from_letter(
            session,
            user=sender,
            name=name,
            age=sender_age,
            photo_file_id=sender_photo_file_id,
            adult_confirmed=True,
        )

    mr = MessageRequest(
        profile_id=profile.id,
        sender_user_id=sender.id,
        text=cleaned,
        text_translated=translated,
        sender_name=name,
        sender_age=sender_age,
        sender_photo_file_id=sender_photo_file_id,
        status=MessageRequestStatus.PENDING.value,
        paid_at_send=False,
        credit_held=0,
    )
    session.add(mr)
    await session.flush()
    await _charge_send(session, sender=sender, mr=mr)
    await session.commit()

    mr = await get_message_request(session, mr.id)
    assert mr is not None
    if recipient:
        await notify_new_letter(settings, recipient=recipient, request=mr)
    return mr


async def translate_text_safe(
    text: str,
    *,
    target_language: str,
    source_language: str,
    settings: Settings,
) -> str | None:
    from app.services.translate import translate_text

    return await translate_text(
        text,
        target_language=target_language,
        source_language=source_language,
        api_key=settings.translation_api_key,
        model=settings.openai_translate_model,
    )


async def list_inbox(session: AsyncSession, user: User) -> list[MessageRequest]:
    """Incoming letters for the user's profile + outgoing requests."""
    result = await session.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    conditions = [MessageRequest.sender_user_id == user.id]
    if profile:
        conditions.append(MessageRequest.profile_id == profile.id)
    stmt = (
        select(MessageRequest)
        .where(or_(*conditions))
        .options(
            selectinload(MessageRequest.profile).selectinload(Profile.user),
            selectinload(MessageRequest.profile).selectinload(Profile.photos),
            selectinload(MessageRequest.sender),
        )
        .order_by(MessageRequest.created_at.desc())
        .limit(100)
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def reject_message_request(
    session: AsyncSession,
    settings: Settings,
    *,
    mr: MessageRequest,
    actor: User,
) -> MessageRequest:
    if mr.profile is None or mr.profile.user_id != actor.id:
        raise MessageServiceError("forbidden", "Only recipient can reject")
    if not await has_unlimited(session, actor.id):
        raise MessageServiceError("need_plus", "Dreamers Plus required to manage letters")
    if mr.status != MessageRequestStatus.PENDING.value:
        raise MessageServiceError("bad_status", "Request is not pending")
    refunded = await refund_held_credit(session, mr=mr, note="letter_rejected_refund")
    mr.status = MessageRequestStatus.REJECTED.value
    mr.responded_at = datetime.now(timezone.utc)
    # «Не интересно» = убрать из входящих у получателя (как скрытое / удалённое).
    mr.hidden_by_recipient = True
    session.add(mr)
    await session.commit()
    mr = await get_message_request(session, mr.id)
    assert mr is not None
    if mr.sender:
        await notify_recipient_rejected(
            settings, initiator=mr.sender, request=mr, credit_refunded=refunded
        )
    return mr


async def reply_message_request(
    session: AsyncSession,
    settings: Settings,
    *,
    mr: MessageRequest,
    actor: User,
    reply_text: str,
) -> MessageRequest:
    if mr.profile is None or mr.profile.user_id != actor.id:
        raise MessageServiceError("forbidden", "Only recipient can reply")
    if not await has_unlimited(session, actor.id):
        raise MessageServiceError("need_plus", "Dreamers Plus required to read and reply")
    if mr.status not in {
        MessageRequestStatus.PENDING.value,
        MessageRequestStatus.EXPIRED.value,
    }:
        raise MessageServiceError("bad_status", "Request cannot accept a reply")
    cleaned = (reply_text or "").strip()
    if len(cleaned) < 1:
        raise MessageServiceError("text_short", "Reply too short")
    if len(cleaned) > 1200:
        raise MessageServiceError("text_long", "Reply too long")
    if contains_contact_info(cleaned):
        raise MessageServiceError("contact_forbidden", "Contact details are not allowed")

    source_lang = _lang(actor)
    target_lang = _lang(mr.sender, _counterpart_lang(source_lang))
    translated = await translate_text_safe(
        cleaned,
        target_language=target_lang,
        source_language=source_lang,
        settings=settings,
    )
    mr.reply_text = cleaned
    mr.reply_text_translated = translated
    mr.responded_at = datetime.now(timezone.utc)
    session.add(mr)

    # Auto-open with Plus or remaining gift; otherwise initiator must buy Plus.
    mr.status = MessageRequestStatus.REPLIED.value
    await session.commit()
    mr = await get_message_request(session, mr.id)
    assert mr is not None
    if mr.sender:
        from app.services.registration import gifts_remaining

        sender = mr.sender
        if await has_unlimited(session, sender.id) or gifts_remaining(sender) > 0:
            mr = await unlock_with_credit(session, settings, mr=mr, actor=sender)
            await session.refresh(sender)
            await notify_initiator_chat_opened(settings, initiator=sender, request=mr)
        else:
            await notify_initiator_pay_to_unlock(settings, initiator=sender, request=mr)
    return mr


async def unlock_with_credit(
    session: AsyncSession,
    settings: Settings,
    *,
    mr: MessageRequest,
    actor: User,
    payment_id: int | None = None,
) -> MessageRequest:
    """Open chat after reply: Plus (free) or spend one gift. Credits no longer work."""
    from app.services.registration import consume_gift_marker, gifts_remaining

    if mr.sender_user_id != actor.id:
        raise MessageServiceError("forbidden", "Only initiator can unlock")
    if mr.status in {
        MessageRequestStatus.UNLOCKED.value,
        MessageRequestStatus.CHATTING.value,
    }:
        return mr
    if mr.profile is None:
        raise MessageServiceError("profile_deleted", "The profile was taken down and deleted")
    if mr.status != MessageRequestStatus.REPLIED.value:
        raise MessageServiceError("bad_status", "Wait for a reply before paying")
    unlimited = await has_unlimited(session, actor.id)
    from_gift = False
    if not unlimited:
        if gifts_remaining(actor) < 1:
            raise MessageServiceError("need_plus", "Dreamers Plus required to open chat")
        from_gift = consume_gift_marker(actor)
        session.add(actor)
    mr.credit_held = 0
    now = datetime.now(timezone.utc)
    mr.status = MessageRequestStatus.CHATTING.value
    mr.unlocked_at = now
    mr.unlock_from_gift = from_gift
    if payment_id:
        mr.charged_payment_id = payment_id
    session.add(mr)
    await _seed_chat_from_letter(session, mr)

    await session.commit()
    mr = await get_message_request(session, mr.id)
    assert mr is not None
    await notify_parties_unlocked(settings, request=mr)
    return mr


async def expire_due_letters(session: AsyncSession, settings: Settings) -> int:
    """Refund + close pending letters with no reply within the timeout."""
    days = max(1, settings.message_reply_timeout_days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(MessageRequest)
        .where(
            MessageRequest.status == MessageRequestStatus.PENDING.value,
            MessageRequest.created_at <= cutoff,
        )
        .options(
            selectinload(MessageRequest.profile).selectinload(Profile.user),
            selectinload(MessageRequest.sender),
        )
        .order_by(MessageRequest.created_at.asc())
        .limit(50)
    )
    rows = list(result.scalars().all())
    expired = 0
    for mr in rows:
        await refund_held_credit(session, mr=mr, note="letter_timeout_refund")
        mr.status = MessageRequestStatus.EXPIRED.value
        session.add(mr)
        await session.commit()
        refreshed = await get_message_request(session, mr.id)
        if refreshed is not None:
            await notify_letter_expired(settings, request=refreshed)
        expired += 1
    return expired


async def send_chat_message(
    session: AsyncSession,
    settings: Settings,
    *,
    mr: MessageRequest,
    actor: User,
    text: str,
) -> ChatMessage:
    if mr.profile is None:
        raise MessageServiceError("profile_deleted", "The profile was taken down and deleted")
    owner_id = mr.profile.user_id
    if actor.id not in {mr.sender_user_id, owner_id}:
        raise MessageServiceError("forbidden", "Not a participant")
    if mr.status not in {
        MessageRequestStatus.UNLOCKED.value,
        MessageRequestStatus.CHATTING.value,
    }:
        raise MessageServiceError("locked", "Chat is not unlocked yet")

    cleaned = (text or "").strip()
    if not cleaned:
        raise MessageServiceError("text_short", "Empty message")
    if len(cleaned) > 2000:
        raise MessageServiceError("text_long", "Message too long")

    source_lang = _lang(actor)
    other = mr.sender if actor.id == owner_id else mr.profile.user
    target_lang = _lang(other, _counterpart_lang(source_lang))
    translated = await translate_text_safe(
        cleaned,
        target_language=target_lang,
        source_language=source_lang,
        settings=settings,
    )
    if mr.status == MessageRequestStatus.UNLOCKED.value:
        mr.status = MessageRequestStatus.CHATTING.value
        session.add(mr)

    msg = ChatMessage(
        message_request_id=mr.id,
        sender_user_id=actor.id,
        text=cleaned,
        text_translated=translated,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def list_chat_messages(session: AsyncSession, mr: MessageRequest) -> list[ChatMessage]:
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.message_request_id == mr.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    return list(result.scalars().all())


async def inbox_pending_count(session: AsyncSession, user: User) -> int:
    result = await session.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        return 0
    count = await session.execute(
        select(func.count())
        .select_from(MessageRequest)
        .where(
            MessageRequest.profile_id == profile.id,
            MessageRequest.status.in_(
                [
                    MessageRequestStatus.PENDING.value,
                    MessageRequestStatus.EXPIRED.value,
                ]
            ),
        )
    )
    return int(count.scalar_one())


async def share_own_telegram(
    session: AsyncSession,
    settings: Settings,
    *,
    mr: MessageRequest,
    actor: User,
) -> MessageRequest:
    """One-sided: actor reveals their own @username to the peer."""
    if mr.profile is None:
        raise MessageServiceError("profile_deleted", "Profile deleted")
    owner_id = mr.profile.user_id
    if actor.id not in {mr.sender_user_id, owner_id}:
        raise MessageServiceError("forbidden", "Not a participant")
    if mr.status not in {
        MessageRequestStatus.UNLOCKED.value,
        MessageRequestStatus.CHATTING.value,
    }:
        raise MessageServiceError("locked", "Chat is not unlocked yet")
    uname = (actor.telegram_username or "").strip().lstrip("@")
    if not uname:
        raise MessageServiceError("no_username", "Telegram username required")

    now = datetime.now(timezone.utc)
    if actor.id == mr.sender_user_id:
        mr.sender_telegram_shared_at = now
    else:
        mr.recipient_telegram_shared_at = now
        if mr.profile and not (mr.profile.telegram_username or "").strip():
            mr.profile.telegram_username = uname
            session.add(mr.profile)
    session.add(mr)
    await session.commit()
    mr = await get_message_request(session, mr.id)
    assert mr is not None
    from app.services.notify import notify_telegram_shared

    await notify_telegram_shared(settings, request=mr, sharer=actor)
    return mr


async def hide_message_thread(
    session: AsyncSession,
    *,
    mr: MessageRequest,
    actor: User,
) -> MessageRequest:
    if mr.profile is None and mr.sender_user_id != actor.id:
        raise MessageServiceError("forbidden", "Not a participant")
    owner_id = mr.profile.user_id if mr.profile else None
    if actor.id == mr.sender_user_id:
        mr.hidden_by_sender = True
    elif owner_id is not None and actor.id == owner_id:
        mr.hidden_by_recipient = True
    else:
        raise MessageServiceError("forbidden", "Not a participant")
    session.add(mr)
    await session.commit()
    return mr
