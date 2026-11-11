"""OpenAI vision: person present and not a group photo."""

from __future__ import annotations

import base64
import logging
from typing import Literal

import httpx

from app.services.translate import DEFAULT_MODEL, OPENAI_CHAT_URL

logger = logging.getLogger(__name__)

PhotoCheck = Literal["ok", "no_person", "group"]


class VisionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def assess_profile_photo(
    image_bytes: bytes,
    *,
    mime: str,
    api_key: str | None,
    model: str = DEFAULT_MODEL,
) -> PhotoCheck:
    """Classify photo: ok (exactly one person), no_person, or group (2+ people).

    If no API key or the API fails, allow the upload (`ok`) so local/dev keeps working.
    """
    if not api_key:
        return "ok"
    if not image_bytes:
        raise VisionError("photo_required", "Empty image")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    payload = {
        "model": model,
        "max_tokens": 10,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Count how many distinct real human people are clearly visible "
                            "in this photo (face and/or body). Ignore statues, drawings, "
                            "posters and tiny background silhouettes.\n"
                            "Reply with exactly one word:\n"
                            "NONE — no real person\n"
                            "ONE — exactly one person\n"
                            "MULTI — two or more people"
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
                ],
            }
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENAI_CHAT_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.exception("Vision API failed")
        return "ok"

    text = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    ).strip().upper()
    token = text.split()[0] if text else ""
    token = token.strip(".,:;!\"'")
    if token.startswith("MULTI") or token in {"MANY", "GROUP", "TWO", "2+"}:
        return "group"
    if token.startswith("NONE") or token == "NO" or token == "ZERO":
        return "no_person"
    if token.startswith("ONE") or token == "1" or token == "YES":
        return "ok"
    # Ambiguous model reply — be strict on MULTI mentions, else allow.
    if "MULTI" in text or "TWO" in text or "GROUP" in text:
        return "group"
    if "NONE" in text or text.startswith("NO"):
        return "no_person"
    return "ok"


async def photo_has_person(
    image_bytes: bytes,
    *,
    mime: str,
    api_key: str | None,
    model: str = DEFAULT_MODEL,
) -> bool:
    """Backward-compatible helper: True if at least one person is present and not a group. """
    result = await assess_profile_photo(
        image_bytes, mime=mime, api_key=api_key, model=model
    )
    return result == "ok"
