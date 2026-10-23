"""Legacy channel anketa: admin entry + Mini App invite, no userbot."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import LegacyAnketa, LegacyAnketaStatus, User
from app.services.notify import notify_legacy_invite
from app.services.telegram_api import get_bot_username


class LegacyServiceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def list_legacy(session: AsyncSession, *, status: str | None = None) -> list[LegacyAnketa]:
    stmt = select(LegacyAnketa).order_by(LegacyAnketa.id.desc()).limit(200)
    if status:
        stmt = stmt.where(LegacyAnketa.status == status)
    return list((await session.execute(stmt)).scalars().all())


async def create_legacy(
    session: AsyncSession,
    *,
    name: str,
    gender: str | None = None,
    city: str | None = None,
    age: int | None = None,
    channel_message_id: int | None = None,
    telegram_username: str | None = None,
    notes: str | None = None,
) -> LegacyAnketa:
    cleaned = (name or "").strip()
    if len(cleaned) < 2:
        raise LegacyServiceError("name", "Name is required")
    nick = (telegram_username or "").strip().lstrip("@") or None
    row = LegacyAnketa(
        name=cleaned[:255],
        gender=gender if gender in {"male", "female"} else None,
        city=(city or "").strip()[:255] or None,
        age=age,
        channel_message_id=channel_message_id,
        telegram_username=nick,
        notes=(notes or "").strip() or None,
        status=LegacyAnketaStatus.PENDING.value,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def invite_legacy(session: AsyncSession, settings: Settings, row: LegacyAnketa) -> LegacyAnketa:
    if not row.invite_token:
        row.invite_token = secrets.token_urlsafe(16)
    row.status = LegacyAnketaStatus.INVITED.value
    row.invited_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    bot_username = await get_bot_username(settings)
    link = None
    if bot_username:
        link = f"https://t.me/{bot_username}?startapp=legacy_{row.invite_token}"
    else:
        link = f"{settings.webapp_url.rstrip('/')}/?startapp=legacy_{row.invite_token}"
    await notify_legacy_invite(settings, anketa=row, link=link)
    return row


async def skip_legacy(session: AsyncSession, row: LegacyAnketa) -> LegacyAnketa:
    row.status = LegacyAnketaStatus.SKIPPED.value
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def claim_legacy(session: AsyncSession, *, token: str, user: User) -> LegacyAnketa:
    cleaned = (token or "").strip()
    result = await session.execute(select(LegacyAnketa).where(LegacyAnketa.invite_token == cleaned))
    row = result.scalar_one_or_none()
    if row is None:
        raise LegacyServiceError("not_found", "Invite not found")
    if row.status == LegacyAnketaStatus.ACTIVATED.value and row.activated_user_id != user.id:
        raise LegacyServiceError("taken", "Already activated by another user")
    row.status = LegacyAnketaStatus.ACTIVATED.value
    row.activated_user_id = user.id
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
