"""AI-moderate discussion-group comments (not auto-forwards)."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from app.config import get_settings
from app.database import async_session_factory
from app.models import CommentDecision
from app.services.comments_ai import add_strike, classify_comment, record_comment

logger = logging.getLogger(__name__)
router = Router(name="comments")


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), ~F.is_automatic_forward)
async def on_group_comment(message: Message) -> None:
    if message.from_user is None or message.from_user.is_bot:
        return
    settings = get_settings()
    if settings.discussion_chat_id and message.chat.id != settings.discussion_chat_id:
        return
    text = (message.text or message.caption or "").strip()
    if not text:
        return

    should_delete, reason = await classify_comment(
        text,
        api_key=settings.translation_api_key,
        model=settings.openai_translate_model,
    )
    async with async_session_factory() as session:
        await record_comment(
            session,
            chat_id=message.chat.id,
            telegram_user_id=message.from_user.id,
            telegram_message_id=message.message_id,
            username=message.from_user.username,
            text=text,
            decision=CommentDecision.DELETE.value if should_delete else CommentDecision.KEEP.value,
            reason=reason,
        )
        if should_delete:
            await add_strike(
                session,
                settings,
                telegram_user_id=message.from_user.id,
                chat_id=message.chat.id,
            )
        await session.commit()

    if should_delete:
        try:
            await message.delete()
        except Exception:
            logger.exception("Failed to delete group comment %s", message.message_id)
