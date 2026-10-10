"""Thin Telegram Bot API client (httpx) used by API and scheduler."""

from __future__ import annotations

import json
import logging
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class TelegramApiError(Exception):
    def __init__(self, message: str, *, response: dict | None = None):
        super().__init__(message)
        self.response = response


def _is_placeholder_token(token: str) -> bool:
    return not token or token.startswith("0000000000")


async def telegram_call(
    settings: Settings,
    method: str,
    *,
    json: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if _is_placeholder_token(settings.bot_token):
        logger.info("Skip Telegram %s: placeholder bot token", method)
        return {"ok": True, "result": {"message_id": 0}, "skipped": True}

    url = f"https://api.telegram.org/bot{settings.bot_token}/{method}"
    async with httpx.AsyncClient(timeout=180.0 if files else 60.0) as client:
        if files:
            response = await client.post(url, data=data or {}, files=files)
        else:
            response = await client.post(url, json=json or {})
        payload = response.json()
    if not payload.get("ok"):
        raise TelegramApiError(
            f"Telegram {method} failed: {payload.get('description', response.status_code)}",
            response=payload,
        )
    return payload


async def send_message(
    settings: Settings,
    chat_id: int,
    text: str,
    *,
    reply_markup: dict | None = None,
    parse_mode: str | None = "HTML",
    disable_link_preview: bool = False,
) -> dict[str, Any]:
    body: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        body["parse_mode"] = parse_mode
    if reply_markup:
        body["reply_markup"] = reply_markup
    if disable_link_preview:
        body["link_preview_options"] = {"is_disabled": True}
    return await telegram_call(settings, "sendMessage", json=body)


async def send_invoice_stars(
    settings: Settings,
    chat_id: int,
    *,
    title: str,
    description: str,
    payload: str,
    stars_amount: int,
    label: str | None = None,
) -> dict[str, Any]:
    body = {
        "chat_id": chat_id,
        "title": title[:32],
        "description": description[:255],
        "payload": payload[:128],
        "currency": "XTR",
        "provider_token": "",
        "prices": [{"label": label or title[:32], "amount": stars_amount}],
    }
    return await telegram_call(settings, "sendInvoice", json=body)


async def send_photo_file(
    settings: Settings,
    chat_id: int,
    photo_path: Path,
    *,
    caption: str | None = None,
    reply_markup: dict | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption
        data["parse_mode"] = "HTML"
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    with photo_path.open("rb") as fh:
        return await telegram_call(
            settings,
            "sendPhoto",
            data=data,
            files={"photo": (photo_path.name, fh, "image/jpeg")},
        )


async def send_photo_media(
    settings: Settings,
    chat_id: int,
    media: str,
    *,
    caption: str | None = None,
    reply_markup: dict | None = None,
) -> dict[str, Any]:
    """media is Telegram file_id or URL."""
    body: dict[str, Any] = {"chat_id": chat_id, "photo": media}
    if caption:
        body["caption"] = caption
        body["parse_mode"] = "HTML"
    if reply_markup:
        body["reply_markup"] = reply_markup
    return await telegram_call(settings, "sendPhoto", json=body)


async def send_media_group(
    settings: Settings,
    chat_id: int,
    media: list[dict[str, Any]],
) -> dict[str, Any]:
    return await telegram_call(
        settings,
        "sendMediaGroup",
        json={"chat_id": chat_id, "media": media},
    )


async def send_photo_album(
    settings: Settings,
    chat_id: int,
    photos: list[str | Path],
    *,
    caption: str | None = None,
) -> dict[str, Any]:
    """Send 2–10 photos as one album. Items are Telegram file_ids/URLs or local paths."""
    return await send_media_album(
        settings, chat_id, [("photo", photo) for photo in photos], caption=caption
    )


async def send_media_album(
    settings: Settings,
    chat_id: int,
    items: list[tuple[str, str | Path]],
    *,
    caption: str | None = None,
) -> dict[str, Any]:
    """Send 2–10 photos/videos as one album; caption goes on the first item."""
    media: list[dict[str, Any]] = []
    local_paths: dict[str, tuple[Path, str]] = {}
    for idx, (kind, source) in enumerate(items):
        if isinstance(source, Path):
            attach_name = f"{kind}{idx}"
            mime = "video/mp4" if kind == "video" else "image/jpeg"
            local_paths[attach_name] = (source, mime)
            item: dict[str, Any] = {"type": kind, "media": f"attach://{attach_name}"}
        else:
            item = {"type": kind, "media": source}
        if kind == "video":
            item["supports_streaming"] = True
        if idx == 0 and caption:
            item["caption"] = caption
            item["parse_mode"] = "HTML"
        media.append(item)

    if not local_paths:
        return await send_media_group(settings, chat_id, media)

    with ExitStack() as stack:
        files = {
            name: (path.name, stack.enter_context(path.open("rb")), mime)
            for name, (path, mime) in local_paths.items()
        }
        return await telegram_call(
            settings,
            "sendMediaGroup",
            data={"chat_id": str(chat_id), "media": json.dumps(media)},
            files=files,
        )


async def delete_message(
    settings: Settings,
    chat_id: int,
    message_id: int,
) -> dict[str, Any]:
    return await telegram_call(
        settings,
        "deleteMessage",
        json={"chat_id": chat_id, "message_id": message_id},
    )


async def get_bot_info(settings: Settings) -> dict:
    try:
        payload = await telegram_call(settings, "getMe", json={})
        return payload.get("result") or {}
    except Exception:
        logger.exception("getMe failed")
        return {}


async def get_bot_username(settings: Settings) -> str | None:
    return (await get_bot_info(settings)).get("username")


async def bot_has_main_web_app(settings: Settings) -> bool:
    return bool((await get_bot_info(settings)).get("has_main_web_app"))


async def upload_local_photo(
    settings: Settings,
    chat_id: int,
    photo_path: Path,
) -> str | None:
    """Upload a local photo to Telegram and return file_id (best-effort)."""
    result = await send_photo_file(settings, chat_id, photo_path)
    if result.get("skipped"):
        return None
    photos = result.get("result", {}).get("photo") or []
    if not photos:
        return None
    return photos[-1].get("file_id")
