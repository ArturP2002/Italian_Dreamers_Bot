"""Take a published profile down from the channel and delete its data.

A new publication starts from scratch: questionnaire, moderation and payment.
The user account, payments, credits and complaints stay; letters stay with the
other side (read-only) and a short journal entry is kept for the admins.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import (
    MessageRequest,
    MessageRequestStatus,
    Profile,
    ProfileStatus,
    ProfileTakedown,
    User,
)
from app.services.channel import MEDIA_PROFILES, delete_publication_messages
from app.services.greeting_video import video_path
from app.services.notify import notify_user_profile_deleted
from app.services.splash import SPLASH_DIR

logger = logging.getLogger(__name__)

OPEN_CHAT_STATUSES = (MessageRequestStatus.UNLOCKED.value, MessageRequestStatus.CHATTING.value)
UNANSWERED_STATUSES = (MessageRequestStatus.PENDING.value, MessageRequestStatus.REPLIED.value)


@dataclass
class TakedownOutcome:
    entry: ProfileTakedown
    # False for profiles published before all channel message ids were stored.
    complete: bool


async def _photo_ids_still_in_use(session: AsyncSession, file_ids: list[str]) -> set[str]:
    """Letters the owner sent to others reuse her profile photo; those files must stay."""
    if not file_ids:
        return set()
    in_letters = await session.execute(
        select(MessageRequest.sender_photo_file_id).where(MessageRequest.sender_photo_file_id.in_(file_ids))
    )
    in_identity = await session.execute(
        select(User.stated_photo_file_id).where(User.stated_photo_file_id.in_(file_ids))
    )
    return {fid for fid in [*in_letters.scalars(), *in_identity.scalars()] if fid}


async def _profile_files(session: AsyncSession, profile: Profile) -> list[Path]:
    photo_ids = [p.file_id for p in profile.photos or []]
    in_use = await _photo_ids_still_in_use(session, photo_ids)
    files = [
        MEDIA_PROFILES / fid.removeprefix("local:")
        for fid in photo_ids
        if fid.startswith("local:") and fid not in in_use
    ]
    video = video_path(profile.greeting_video_file_id)
    if video is not None:
        files.append(video)
    files.append(SPLASH_DIR / f"splash_{profile.id}.jpg")
    return files


async def take_down_and_delete_profile(
    session: AsyncSession,
    settings: Settings,
    *,
    profile: Profile,
    admin: User | None,
    notify_user: bool,
) -> TakedownOutcome:
    if profile.status != ProfileStatus.PUBLISHED.value:
        raise ValueError("Only published profiles can be taken down")

    channel = await delete_publication_messages(settings, profile)
    now = datetime.now(timezone.utc)
    owner = profile.user
    profile_name = profile.name

    closed = await session.execute(
        update(MessageRequest)
        .where(
            MessageRequest.profile_id == profile.id,
            MessageRequest.status.in_(UNANSWERED_STATUSES),
        )
        .values(status=MessageRequestStatus.CLOSED.value)
    )
    open_chats = await session.execute(
        select(func.count())
        .select_from(MessageRequest)
        .where(
            MessageRequest.profile_id == profile.id,
            MessageRequest.status.in_(OPEN_CHAT_STATUSES),
        )
    )
    await session.execute(
        update(MessageRequest)
        .where(MessageRequest.profile_id == profile.id)
        .values(
            profile_name_snapshot=profile_name,
            profile_owner_user_id=profile.user_id,
            profile_deleted_at=now,
        )
    )

    files = await _profile_files(session, profile)
    entry = ProfileTakedown(
        profile_id=profile.id,
        user_id=owner.id if owner else None,
        telegram_id=owner.telegram_id if owner else None,
        telegram_username=profile.telegram_username or (owner.telegram_username if owner else None),
        name=profile_name,
        age=profile.age,
        gender=profile.gender,
        city=profile.city,
        country=profile.country,
        published_at=profile.published_at,
        admin_user_id=admin.id if admin else None,
        deleted_messages=channel.deleted,
        failed_messages=len(channel.failed),
        closed_letters=closed.rowcount or 0,
        open_chats=int(open_chats.scalar_one()),
    )
    session.add(entry)
    await session.delete(profile)
    await session.commit()

    for path in files:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Failed to delete file %s of profile %s", path, entry.profile_id)

    if notify_user and owner is not None:
        entry.user_notified = await notify_user_profile_deleted(
            settings, user=owner, profile_name=profile_name
        )
        session.add(entry)
        await session.commit()

    await session.refresh(entry, attribute_names=["admin"])
    return TakedownOutcome(entry=entry, complete=channel.complete)


async def list_takedowns(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[ProfileTakedown], int]:
    total = await session.execute(select(func.count()).select_from(ProfileTakedown))
    rows = await session.execute(
        select(ProfileTakedown)
        .options(selectinload(ProfileTakedown.admin))
        .order_by(ProfileTakedown.created_at.desc(), ProfileTakedown.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows.scalars().all()), int(total.scalar_one())
