"""Daily «Наши новенькие» collage for the channel + app list."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import Profile, ProfileStatus, Subscription, SubscriptionStatus
from app.services.channel import MEDIA_PROFILES
from app.services.entitlements import utcnow
from app.services.telegram_api import get_bot_username, send_message, send_photo_album, send_photo_file

logger = logging.getLogger(__name__)

ROME = ZoneInfo("Europe/Rome")
COLLAGE_DIR = Path(__file__).resolve().parents[2] / "media" / "newcomers"
COLLAGE_DIR.mkdir(parents=True, exist_ok=True)

CELL = 360
COLS = 5
ROWS = 2


def _rome_today() -> str:
    return datetime.now(ROME).date().isoformat()


def _open_local_photo(file_id: str) -> Image.Image | None:
    if not file_id.startswith("local:"):
        return None
    rel = file_id.removeprefix("local:")
    path = MEDIA_PROFILES / rel if not rel.startswith("letters/") else Path(__file__).resolve().parents[2] / "media" / rel
    if not path.exists():
        return None
    try:
        img = Image.open(path).convert("RGB")
        return img
    except OSError:
        return None


def _cover_crop(img: Image.Image, size: int) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = max(0, int((h - side) * 0.18))
    crop = img.crop((left, top, left + side, top + side))
    return crop.resize((size, size), Image.Resampling.LANCZOS)


def build_collage(photos: list[Image.Image]) -> Image.Image:
    canvas = Image.new("RGB", (COLS * CELL, ROWS * CELL), (26, 21, 17))
    for i, photo in enumerate(photos[: COLS * ROWS]):
        r, c = divmod(i, COLS)
        canvas.paste(_cover_crop(photo, CELL), (c * CELL, r * CELL))
    return canvas


async def _eligible_newcomers(session: AsyncSession, *, batch_date: str) -> list[Profile]:
    now = utcnow()
    plus_ids = (
        select(Subscription.user_id)
        .where(
            Subscription.expires_at > now,
            Subscription.status.in_(
                [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.CANCELED.value]
            ),
        )
        .distinct()
    )
    result = await session.execute(
        select(Profile)
        .where(
            Profile.status.in_([ProfileStatus.QUEUED.value, ProfileStatus.PUBLISHED.value]),
            Profile.user_id.in_(plus_ids),
            Profile.newcomers_collage_at.is_(None),
            # Not yet given a solo channel post (or queued waiting).
            Profile.channel_message_id.is_(None),
        )
        .options(selectinload(Profile.photos), selectinload(Profile.user))
        .order_by(Profile.paid_at.desc().nullslast(), Profile.approved_at.desc().nullslast())
        .limit(60)
    )
    return list(result.scalars().unique().all())


def _pick_balanced(profiles: list[Profile], n: int = 10) -> list[Profile]:
    women = [p for p in profiles if p.gender == "female"]
    men = [p for p in profiles if p.gender == "male"]
    half = n // 2
    picked: list[Profile] = []
    picked.extend(women[:half])
    picked.extend(men[:half])
    # Fill remainder from either side
    rest = [p for p in profiles if p not in picked]
    while len(picked) < n and rest:
        picked.append(rest.pop(0))
    return picked[:n]


async def list_today_newcomers(session: AsyncSession) -> list[Profile]:
    today = _rome_today()
    result = await session.execute(
        select(Profile)
        .where(Profile.newcomers_batch_date == today)
        .options(selectinload(Profile.photos))
        .order_by(Profile.newcomers_collage_at.desc().nullslast())
        .limit(40)
    )
    return list(result.scalars().unique().all())


async def publish_daily_newcomers(session: AsyncSession, settings: Settings) -> dict:
    """Build collage batches and post to channel. Returns stats."""
    today = _rome_today()
    pool = await _eligible_newcomers(session, batch_date=today)
    if not pool:
        return {"batches": 0, "faces": 0}

    batches: list[list[Profile]] = []
    remaining = list(pool)
    while remaining:
        batch = _pick_balanced(remaining, 10)
        if not batch:
            break
        batches.append(batch)
        remaining = [p for p in remaining if p not in batch]

    if not batches:
        return {"batches": 0, "faces": 0}

    collage_paths: list[Path] = []
    marked: list[Profile] = []
    now = utcnow()
    for idx, batch in enumerate(batches):
        images: list[Image.Image] = []
        for profile in batch:
            photos = sorted(profile.photos or [], key=lambda p: p.position)
            if not photos:
                continue
            img = _open_local_photo(photos[0].file_id)
            if img is None:
                continue
            images.append(img)
            profile.newcomers_collage_at = now
            profile.newcomers_batch_date = today
            session.add(profile)
            marked.append(profile)
        if not images:
            continue
        collage = build_collage(images)
        out = COLLAGE_DIR / f"newcomers_{today}_{idx + 1}.jpg"
        collage.save(out, quality=90)
        collage_paths.append(out)

    await session.commit()
    if not collage_paths:
        return {"batches": 0, "faces": 0}

    chat_id = settings.channel_id
    if not chat_id:
        logger.warning("CHANNEL_ID missing — newcomers collage saved locally only")
        return {"batches": len(collage_paths), "faces": len(marked), "posted": False}

    bot_username = await get_bot_username(settings)
    try:
        if len(collage_paths) == 1:
            await send_photo_file(
                settings, chat_id, collage_paths[0], caption="✨ Наши новенькие"
            )
        else:
            await send_photo_album(
                settings, chat_id, collage_paths, caption="✨ Наши новенькие"
            )
    except Exception:
        logger.exception("Failed to post newcomers collage")
        return {"batches": len(collage_paths), "faces": len(marked), "posted": False}

    link = (
        f"https://t.me/{bot_username}?startapp=newcomers"
        if bot_username
        else f"{settings.webapp_url.rstrip('/')}/newcomers"
    )
    btn = {
        "inline_keyboard": [[{"text": "Смотреть и написать", "url": link}]]
    }
    try:
        await send_message(
            settings,
            chat_id,
            "Смотри новеньких в приложении и пиши 💌",
            reply_markup=btn,
        )
    except Exception:
        logger.exception("Failed newcomers follow-up button")

    return {"batches": len(collage_paths), "faces": len(marked), "posted": True}
