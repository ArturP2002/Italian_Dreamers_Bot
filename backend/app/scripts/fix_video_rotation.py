"""Re-encode stored greeting videos that rely on a rotation flag.

Run once inside the api container:
    python -m app.scripts.fix_video_rotation
Posts already in the channel stay as they are; only future publications use the fixed files.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.database import async_session_factory, engine
from app.models import Profile
from app.services.greeting_video import normalize_to_mp4, probe_video, video_path

logger = logging.getLogger("fix_video_rotation")


async def main() -> None:
    fixed = skipped = failed = 0
    async with async_session_factory() as session:
        profiles = (
            await session.scalars(select(Profile).where(Profile.greeting_video_file_id.is_not(None)))
        ).all()
        for profile in profiles:
            path = video_path(profile.greeting_video_file_id)
            if path is None:
                continue
            info = await probe_video(path)
            if info is None or not info.rotation:
                skipped += 1
                continue
            final = await normalize_to_mp4(path)
            if final == path:
                logger.warning("Profile %s: re-encode failed, kept %s", profile.id, path.name)
                failed += 1
                continue
            profile.greeting_video_file_id = f"local:{final.name}"
            await session.commit()
            logger.info("Profile %s: %s (rotation %s) -> %s", profile.id, path.name, info.rotation, final.name)
            fixed += 1
    await engine.dispose()
    logger.info("Done: fixed %s, already upright %s, failed %s", fixed, skipped, failed)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
