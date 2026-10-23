"""Callback: check Telegram username after the user created one."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.auth.telegram import TelegramWebAppUser, upsert_user_from_telegram
from app.config import get_settings
from app.database import async_session_factory
from app.services.username_nudge import CHECK_CALLBACK, MISS_TEXT, OK_TEXT, check_and_store_username, _lang

logger = logging.getLogger(__name__)
router = Router(name="username")


@router.callback_query(F.data == CHECK_CALLBACK)
async def on_check_username(query: CallbackQuery) -> None:
    tg_user = query.from_user
    if tg_user is None:
        await query.answer()
        return
    settings = get_settings()
    async with async_session_factory() as session:
        user = await upsert_user_from_telegram(
            session,
            TelegramWebAppUser(
                id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                language_code=tg_user.language_code,
            ),
        )
        username = await check_and_store_username(session, settings, user=user)
        lang = _lang(user)
    if username:
        await query.answer()
        if query.message:
            await query.message.answer(OK_TEXT[lang].format(username=username))
        return
    await query.answer(MISS_TEXT[lang][:180], show_alert=True)
