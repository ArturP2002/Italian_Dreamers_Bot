import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

# Allow `python bot/main.py` locally: shared package lives in backend/app
_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import TelegramObject

from app.auth.telegram import TelegramWebAppUser, upsert_user_from_telegram
from app.config import get_settings
from app.database import async_session_factory
from handlers import broadcast, comments, discussion, info, payments, start, username

logger = logging.getLogger(__name__)


class SyncTelegramUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is not None:
            try:
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
                    if not user.bot_write_access:
                        from datetime import datetime, timezone

                        user.bot_write_access = True
                        user.bot_write_access_at = datetime.now(timezone.utc)
                        session.add(user)
                        await session.commit()
            except Exception:
                logger.exception("Failed to sync Telegram user %s", getattr(tg_user, "id", None))
        return await handler(event, data)


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.message.middleware(SyncTelegramUserMiddleware())
    dispatcher.callback_query.middleware(SyncTelegramUserMiddleware())
    dispatcher.include_router(start.router)
    dispatcher.include_router(broadcast.router)
    dispatcher.include_router(payments.router)
    dispatcher.include_router(username.router)
    dispatcher.include_router(discussion.router)
    dispatcher.include_router(comments.router)
    dispatcher.include_router(info.router)

    try:
        await info.set_bot_commands(bot)
    except Exception:
        logging.exception("Failed to set bot commands")

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
