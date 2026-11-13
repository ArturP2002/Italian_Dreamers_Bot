"""OpenAI vision: person present, not a group photo, face match for verification."""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

import httpx

from app.services.translate import DEFAULT_MODEL, OPENAI_CHAT_URL

logger = logging.getLogger(__name__)

PhotoCheck = Literal["ok", "no_person", "group"]
FaceMatchDecision = Literal["pass", "fail", "review"]


class VisionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FaceMatchResult:
    decision: FaceMatchDecision
    score: int | None
    reason: str


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


async def assess_verification_selfie(
    image_bytes: bytes,
    *,
    mime: str,
    api_key: str | None,
    model: str = DEFAULT_MODEL,
) -> PhotoCheck:
    """Lenient face check for live verification selfies.

    Close-up front-camera frames often confuse the strict profile classifier
    (NONE / MULTI). Here we only reject a clear empty frame / multi-person shot.
    Ambiguous replies pass through — face-match is the real gate.
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
                            "This is a live front-camera selfie for identity verification.\n"
                            "Is there a clearly visible real human face?\n"
                            "Answer with exactly one word:\n"
                            "YES — one human face is visible (close-up selfie is OK)\n"
                            "MULTI — two or more people\n"
                            "NO — no human face visible"
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
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
        logger.exception("Vision selfie check failed")
        return "ok"

    text = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    ).strip().upper()
    token = (text.split()[0] if text else "").strip(".,:;!\"'")
    if token.startswith("MULTI") or "MULTI" in text:
        return "group"
    if token in {"NO", "NONE", "ZERO"} or token.startswith("NO"):
        # Only hard-reject when the model is clearly negative.
        if "YES" in text or "ONE" in text or "FACE" in text:
            return "ok"
        return "no_person"
    return "ok"


def _data_url(image_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _parse_face_match_payload(text: str) -> FaceMatchResult | None:
    raw = (text or "").strip()
    if not raw:
        return None
    # Prefer fenced/JSON object even if the model adds prose around it.
    match = re.search(r"\{[^{}]*\}", raw, flags=re.DOTALL)
    blob = match.group(0) if match else raw
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    verdict = str(data.get("match") or data.get("verdict") or "").strip().lower()
    score_raw = data.get("score")
    reason = str(data.get("reason") or "").strip()[:400]
    score: int | None
    try:
        score = int(round(float(score_raw)))
        score = max(0, min(100, score))
    except (TypeError, ValueError):
        score = None

    if verdict in {"yes", "true", "match", "same", "pass"}:
        decision: FaceMatchDecision = "pass"
    elif verdict in {"no", "false", "different", "fail"}:
        decision = "fail"
    else:
        decision = "review"

    # Soft thresholds: keep grey zone for admin.
    if score is not None:
        if score >= 85:
            decision = "pass"
        elif score <= 55:
            decision = "fail"
        else:
            decision = "review"

    if not reason:
        reason = {
            "pass": "Faces look like the same person",
            "fail": "Faces do not look like the same person",
            "review": "Uncertain face match",
        }[decision]
    return FaceMatchResult(decision=decision, score=score, reason=reason)


async def compare_selfie_to_profile_photos(
    selfie_bytes: bytes,
    *,
    selfie_mime: str,
    profile_photos: list[tuple[bytes, str]],
    api_key: str | None,
    model: str = DEFAULT_MODEL,
) -> FaceMatchResult:
    """Compare a live selfie to profile photos via OpenAI Vision.

    Returns review when API key is missing, photos are missing, or the call fails —
    so admin remains the safe fallback.
    """
    if not api_key:
        return FaceMatchResult(decision="review", score=None, reason="Vision API key missing")
    if not selfie_bytes:
        return FaceMatchResult(decision="fail", score=0, reason="Empty selfie")
    if not profile_photos:
        return FaceMatchResult(decision="review", score=None, reason="No profile photos to compare")

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "You verify a dating-profile selfie.\n"
                "Image 1 is a LIVE selfie just taken by the user.\n"
                "The following images are photos from their dating profile.\n"
                "Decide if the selfie shows the SAME real person as in the profile photos.\n"
                "Ignore clothes, background, makeup, hairstyle changes, glasses if eyes are visible.\n"
                "If the selfie looks like a photo of a screen/print, be cautious and prefer unsure.\n"
                "Reply with ONLY compact JSON, no markdown:\n"
                '{"match":"yes"|"no"|"unsure","score":0-100,"reason":"short English reason"}'
            ),
        },
        {"type": "image_url", "image_url": {"url": _data_url(selfie_bytes, selfie_mime), "detail": "low"}},
    ]
    for photo_bytes, mime in profile_photos[:3]:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _data_url(photo_bytes, mime), "detail": "low"},
            }
        )

    payload = {
        "model": model,
        "max_tokens": 120,
        "messages": [{"role": "user", "content": content}],
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                OPENAI_CHAT_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.exception("Vision face-match API failed")
        return FaceMatchResult(decision="review", score=None, reason="Vision API failed")

    text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    parsed = _parse_face_match_payload(text)
    if parsed is None:
        logger.warning("Unparseable face-match reply: %s", text[:300])
        return FaceMatchResult(decision="review", score=None, reason="Unparseable Vision reply")
    return parsed

