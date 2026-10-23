"""OpenAI vision: is there a person in the photo?"""

from __future__ import annotations

import base64
import logging

import httpx

from app.services.translate import OPENAI_CHAT_URL, DEFAULT_MODEL

logger = logging.getLogger(__name__)


class VisionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def photo_has_person(
    image_bytes: bytes,
    *,
    mime: str,
    api_key: str | None,
    model: str = DEFAULT_MODEL,
) -> bool:
    """Return True if a person is visible. If no API key, skip the check (allow)."""
    if not api_key:
        return True
    if not image_bytes:
        raise VisionError("photo_required", "Empty image")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    payload = {
        "model": model,
        "max_tokens": 20,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Does this photo show a real human person (face or body)? "
                            "Answer only YES or NO."
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
        return True
    text = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    ).strip().upper()
    if text.startswith("NO"):
        return False
    return True
