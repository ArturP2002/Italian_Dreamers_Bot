"""AI moderation of discussion-group comments. Delete only explicit harm. 3 strikes / 24h."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import CommentDecision, GroupComment, GroupStrike
from app.services.telegram_api import telegram_call
from app.services.translate import DEFAULT_MODEL, OPENAI_CHAT_URL

logger = logging.getLogger(__name__)

STRIKE_WINDOW = timedelta(hours=24)
RESTRICT_FOR = timedelta(hours=24)

SYSTEM = (
    "You moderate comments on a bilingual (RU/IT) dating channel discussion group. "
    "Delete ONLY if the comment contains explicit harm: threats of violence, hate speech "
    "targeting a protected group, sexual content involving minors, doxxing (home address / "
    "private phone of a third party), scams asking to send money/crypto, or obvious spam flood. "
    "Keep flirting, compliments, mild insults, contact sharing, jokes, and off-topic chat. "
    "Reply with JSON only: {\"delete\": true or false, \"reason\": \"short English reason\"}."
)


def parse_classifier_reply(text: str) -> tuple[bool, str]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        lowered = raw.lower()
        if lowered.startswith("yes") or '"delete": true' in lowered:
            return True, raw[:200]
        return False, "unparsed"
    delete = bool(data.get("delete"))
    reason = str(data.get("reason") or "")[:200]
    return delete, reason or ("harm" if delete else "keep")


async def classify_comment(text: str, *, api_key: str | None, model: str = DEFAULT_MODEL) -> tuple[bool, str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return False, "empty"
    if not api_key:
        return False, "no_api_key"
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 80,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": cleaned[:2000]},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                OPENAI_CHAT_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.exception("Comment classifier failed")
        return False, "classifier_error"
    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return parse_classifier_reply(content)


async def add_strike(
    session: AsyncSession,
    settings: Settings,
    *,
    telegram_user_id: int,
    chat_id: int,
) -> GroupStrike:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(GroupStrike).where(GroupStrike.telegram_user_id == telegram_user_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = GroupStrike(
            telegram_user_id=telegram_user_id,
            count=0,
            window_started_at=now,
        )
    if row.window_started_at.tzinfo is None:
        row.window_started_at = row.window_started_at.replace(tzinfo=timezone.utc)
    if now - row.window_started_at >= STRIKE_WINDOW:
        row.count = 0
        row.window_started_at = now
    row.count += 1
    session.add(row)
    await session.flush()
    if row.count >= 3:
        until = now + RESTRICT_FOR
        row.restricted_until = until
        row.count = 0
        row.window_started_at = now
        session.add(row)
        try:
            await telegram_call(
                settings,
                "restrictChatMember",
                json={
                    "chat_id": chat_id,
                    "user_id": telegram_user_id,
                    "until_date": int(until.timestamp()),
                    "permissions": {
                        "can_send_messages": False,
                        "can_send_audios": False,
                        "can_send_documents": False,
                        "can_send_photos": False,
                        "can_send_videos": False,
                        "can_send_video_notes": False,
                        "can_send_voice_notes": False,
                        "can_send_polls": False,
                        "can_send_other_messages": False,
                    },
                },
            )
        except Exception:
            logger.exception("Failed to restrict user %s in chat %s", telegram_user_id, chat_id)
    return row


async def record_comment(
    session: AsyncSession,
    *,
    chat_id: int,
    telegram_user_id: int,
    telegram_message_id: int,
    username: str | None,
    text: str,
    decision: str,
    reason: str | None,
) -> GroupComment:
    row = GroupComment(
        chat_id=chat_id,
        telegram_user_id=telegram_user_id,
        telegram_message_id=telegram_message_id,
        username=username,
        text=(text or "")[:4000],
        decision=decision,
        reason=(reason or "")[:512] or None,
    )
    session.add(row)
    await session.flush()
    return row


async def list_comments(
    session: AsyncSession,
    *,
    decision: str | None = None,
    limit: int = 50,
) -> list[GroupComment]:
    stmt = select(GroupComment).order_by(GroupComment.id.desc()).limit(limit)
    if decision:
        stmt = stmt.where(GroupComment.decision == decision)
    return list((await session.execute(stmt)).scalars().all())


async def mark_false_positive(session: AsyncSession, comment_id: int) -> GroupComment | None:
    result = await session.execute(select(GroupComment).where(GroupComment.id == comment_id))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    row.decision = CommentDecision.FALSE_POSITIVE.value
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
