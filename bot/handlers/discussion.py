"""Delete discussion-group copies of album + Write posts; keep splash comments."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from app.config import get_settings
from app.database import async_session_factory
from app.services.discussion import should_delete_auto_forward

logger = logging.getLogger(__name__)
router = Router(name="discussion")


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.is_automatic_forward)
async def on_channel_auto_forward(message: Message) -> None:
    settings = get_settings()
    if settings.discussion_chat_id and message.chat.id != settings.discussion_chat_id:
        return
    origin = message.forward_from_chat
    if origin is None or origin.id != settings.channel_id:
        return
    channel_message_id = message.forward_from_message_id
    if not channel_message_id:
        return
    async with async_session_factory() as session:
        delete = await should_delete_auto_forward(session, int(channel_message_id))
    if not delete:
        return
    try:
        await message.delete()
    except Exception:
        logger.exception(
            "Failed to delete discussion copy of channel message %s", channel_message_id
        )
