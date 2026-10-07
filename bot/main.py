import asyncio
import logging
import sys
from pathlib import Path

# Allow `python bot/main.py` locally: shared package lives in backend/app
_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import get_settings
from handlers import payments, start


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(start.router)
    dispatcher.include_router(payments.router)

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
