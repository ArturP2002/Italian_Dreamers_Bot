"""Message requests, unlock with credits, Mini App bilingual chat."""

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
    ProfileStatus,
    User,
)
from app.services.anti_contact import contains_contact_info
from app.services.notify import (
    notify_initiator_pay_to_unlock,
    notify_new_letter,
    notify_parties_unlocked,
    notify_recipient_rejected,
)
from app.services.translate import translate_text


class MessageServiceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _lang(user: User | None, fallback: str = "ru") -> str:
    if user and user.language_code in {"ru", "it"}:
        return user.language_code
    return fallback


def _counterpart_lang(source: str) -> str:
    return "it" if source == "ru" else "ru"


async def get_published_profile(session: AsyncSession, profile_id: int) -> Profile | None:
    result = await session.execute(
        select(Profile)
        .where(Profile.id == profile_id, Profile.status == ProfileStatus.PUBLISHED.value)
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
    if sender.soft_ban_until and sender.soft_ban_until > now:
        raise MessageServiceError("soft_banned", "Soft-banned temporarily")
    if profile.user_id == sender.id:
        raise MessageServiceError("self", "Cannot write to your own profile")
    if not profile.telegram_username and not (profile.user and profile.user.telegram_username):
        raise MessageServiceError("no_username", "Profile author has no Telegram username")

    pending_pair = await session.execute(
        select(func.count())
        .select_from(MessageRequest)
        .where(
            MessageRequest.profile_id == profile.id,
            MessageRequest.sender_user_id == sender.id,
            MessageRequest.status.in_(
                [
                    MessageRequestStatus.PENDING.value,
                    MessageRequestStatus.REPLIED.value,
                    MessageRequestStatus.UNLOCKED.value,
                    MessageRequestStatus.CHATTING.value,
                ]
            ),
        )
    )
    if int(pending_pair.scalar_one()) > 0:
        raise MessageServiceError("duplicate", "Already have an active request to this profile")

    pending_out = await session.execute(
        select(func.count())
        .select_from(MessageRequest)
        .where(
            MessageRequest.sender_user_id == sender.id,
            MessageRequest.status == MessageRequestStatus.PENDING.value,
        )
    )
    if int(pending_out.scalar_one()) >= settings.rate_max_pending_outgoing:
        raise MessageServiceError("pending_limit", "Too many pending outgoing letters")

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
        await _apply_soft_ban(session, settings, sender)
        raise MessageServiceError("soft_banned", "Hourly contact limit — soft-ban applied")
    if day_count >= settings.rate_contact_per_day:
        await _apply_soft_ban(session, settings, sender)
        raise MessageServiceError("soft_banned", "Daily contact limit — soft-ban applied")


async def _apply_soft_ban(session: AsyncSession, settings: Settings, user: User) -> None:
    until = datetime.now(timezone.utc) + timedelta(hours=settings.rate_soft_ban_hours)
    # Extend if already soft-banned further out
    if user.soft_ban_until and user.soft_ban_until > until:
        return
    user.soft_ban_until = until
    session.add(user)
    await session.commit()
    await session.refresh(user)


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
    translated = await translate_text(
        cleaned,
        target_language=target_lang,
        source_language=source_lang,
        api_key=settings.translation_api_key,
        model=settings.openai_translate_model,
    )

    # Persist light identity on sender for future letters
    if remember_identity:
        sender.stated_name = name
        sender.stated_age = sender_age
        if sender_photo_file_id:
            sender.stated_photo_file_id = sender_photo_file_id
        session.add(sender)

    mr = MessageRequest(
        profile_id=profile.id,
        sender_user_id=sender.id,
        text=cleaned,
        text_translated=translated,
        sender_name=name,
        sender_age=sender_age,
        sender_photo_file_id=sender_photo_file_id,
        status=MessageRequestStatus.PENDING.value,
    )
    session.add(mr)
    await session.commit()

    mr = await get_message_request(session, mr.id)
    assert mr is not None
    if recipient:
        await notify_new_letter(settings, recipient=recipient, request=mr)
    return mr


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
    if mr.status != MessageRequestStatus.PENDING.value:
        raise MessageServiceError("bad_status", "Request is not pending")
    mr.status = MessageRequestStatus.REJECTED.value
    mr.responded_at = datetime.now(timezone.utc)
    session.add(mr)
    await session.commit()
    mr = await get_message_request(session, mr.id)
    assert mr is not None
    if mr.sender:
        await notify_recipient_rejected(settings, initiator=mr.sender, request=mr)
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
    if mr.status != MessageRequestStatus.PENDING.value:
        raise MessageServiceError("bad_status", "Request is not pending")
    cleaned = (reply_text or "").strip()
    if len(cleaned) < 1:
        raise MessageServiceError("text_short", "Reply too short")
    if len(cleaned) > 1200:
        raise MessageServiceError("text_long", "Reply too long")
    if contains_contact_info(cleaned):
        raise MessageServiceError("contact_forbidden", "Contact details are not allowed")

    source_lang = _lang(actor)
    target_lang = _lang(mr.sender, _counterpart_lang(source_lang))
    translated = await translate_text(
        cleaned,
        target_language=target_lang,
        source_language=source_lang,
        api_key=settings.translation_api_key,
        model=settings.openai_translate_model,
    )
    mr.reply_text = cleaned
    mr.reply_text_translated = translated
    mr.status = MessageRequestStatus.REPLIED.value
    mr.responded_at = datetime.now(timezone.utc)
    session.add(mr)
    await session.commit()
    mr = await get_message_request(session, mr.id)
    assert mr is not None
    if mr.sender:
        await notify_initiator_pay_to_unlock(settings, initiator=mr.sender, request=mr)
    return mr


async def unlock_with_credit(
    session: AsyncSession,
    settings: Settings,
    *,
    mr: MessageRequest,
    actor: User,
    payment_id: int | None = None,
) -> MessageRequest:
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
    if actor.message_credits < 1:
        raise MessageServiceError("no_credits", "Not enough message credits")

    actor.message_credits -= 1
    session.add(actor)
    session.add(
        CreditLedgerEntry(
            user_id=actor.id,
            entry_type=LedgerEntryType.SPEND.value,
            delta=-1,
            balance_after=actor.message_credits,
            payment_id=payment_id,
            message_request_id=mr.id,
            note="unlock_message",
        )
    )
    now = datetime.now(timezone.utc)
    mr.status = MessageRequestStatus.CHATTING.value
    mr.unlocked_at = now
    if payment_id:
        mr.charged_payment_id = payment_id
    session.add(mr)

    # Seed chat with the original letter + reply (if not already present)
    existing = await session.execute(
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.message_request_id == mr.id)
    )
    if int(existing.scalar_one()) == 0:
        session.add(
            ChatMessage(
                message_request_id=mr.id,
                sender_user_id=mr.sender_user_id,
                text=mr.text,
                text_translated=mr.text_translated,
            )
        )
        if mr.reply_text:
            session.add(
                ChatMessage(
                    message_request_id=mr.id,
                    sender_user_id=mr.profile.user_id,
                    text=mr.reply_text,
                    text_translated=mr.reply_text_translated,
                )
            )

    await session.commit()
    mr = await get_message_request(session, mr.id)
    assert mr is not None
    await notify_parties_unlocked(settings, request=mr)
    return mr


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
    translated = await translate_text(
        cleaned,
        target_language=target_lang,
        source_language=source_lang,
        api_key=settings.translation_api_key,
        model=settings.openai_translate_model,
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
            MessageRequest.status == MessageRequestStatus.PENDING.value,
        )
    )
    return int(count.scalar_one())
