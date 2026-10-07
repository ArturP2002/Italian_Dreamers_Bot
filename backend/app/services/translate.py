"""OpenAI gpt-4o-mini field / message translation (RU↔IT)."""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"

_LANGUAGE_NAMES = {"it": "Italian", "ru": "Russian"}

_FIELD_INSTRUCTIONS = {
    "name": (
        "a person's first name - transliterate/adapt it to how it would naturally "
        "be written in the target language, do not translate its meaning"
    ),
    "city": (
        "a city name - use the standard exonym/spelling for this city in the target "
        "language (e.g. Moscow -> Mosca in Italian), not a literal translation"
    ),
    "country": (
        "a country name - use the standard exonym for this country in the target "
        "language, not a literal translation"
    ),
    "profession": "a job/profession - translate naturally",
    "about": "a personal bio paragraph - translate naturally, keep the tone warm and personal",
    "desired_partner": (
        "a description of the partner this person is looking for - translate naturally, "
        "keep the tone warm and personal"
    ),
    "cover_answer": (
        "a short dating-profile cover answer (max 70 chars) - translate naturally, "
        "keep punchy tone; stay within 70 characters"
    ),
    "message": (
        "a personal dating message or chat reply between two people - translate naturally, "
        "keep tone warm and sincere, do not add contact details"
    ),
}


class TranslationError(Exception):
    """Raised when the OpenAI API call fails or returns an unexpected response."""


class TranslationNotConfigured(Exception):
    """Raised when a translation is needed but no API key is configured."""


async def translate_fields(
    fields: dict[str, str],
    target_language: str,
    source_language: str,
    api_key: str,
    *,
    model: str = DEFAULT_MODEL,
) -> dict[str, str]:
    keys = list(fields.keys())
    if not keys:
        return {}
    target_name = _LANGUAGE_NAMES.get(target_language, target_language)
    source_name = _LANGUAGE_NAMES.get(source_language, source_language)

    field_notes = "\n".join(
        f'- "{key}": {_FIELD_INSTRUCTIONS.get(key, "translate naturally")}' for key in keys
    )

    prompt = (
        f"Translate each of the following dating-profile fields from {source_name} to {target_name}. "
        "Each field needs different handling, described below. Do not add commentary or explanations, "
        "and return ONLY a JSON object with the exact same keys, each mapped to the resulting text.\n\n"
        f"Field-by-field instructions:\n{field_notes}\n\n"
        "Fields (as JSON):\n"
        + json.dumps({key: fields[key] for key in keys}, ensure_ascii=False)
    )

    schema = {
        "type": "object",
        "properties": {key: {"type": "string"} for key in keys},
        "required": keys,
        "additionalProperties": False,
    }

    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional translator for a bilingual dating app (Russian ↔ Italian). "
                    "Preserve warmth and natural spoken tone. Return valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "translated_fields",
                "strict": True,
                "schema": schema,
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as session:
        response = await session.post(OPENAI_CHAT_URL, headers=headers, json=payload)
        data = response.json()
        if response.status_code != 200:
            message = data.get("error", {}).get("message", f"HTTP {response.status_code}")
            raise TranslationError(f"OpenAI API error: {message}")

    try:
        text = data["choices"][0]["message"]["content"]
        translated = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise TranslationError("Unexpected OpenAI API response") from error

    missing = [key for key in keys if key not in translated]
    if missing:
        raise TranslationError(f"OpenAI response missing fields: {missing}")

    return {key: str(translated[key]) for key in keys}


async def translate_fields_or_passthrough(
    fields: dict[str, str],
    *,
    target_language: str,
    source_language: str,
    api_key: str | None,
    model: str = DEFAULT_MODEL,
) -> dict[str, str]:
    cleaned = {k: (v or "").strip() for k, v in fields.items() if (v or "").strip()}
    if not cleaned:
        return {}
    if source_language == target_language:
        return cleaned
    if not api_key:
        logger.warning("OPENAI_API_KEY missing — using source text as translation")
        return cleaned
    try:
        return await translate_fields(
            cleaned,
            target_language,
            source_language,
            api_key,
            model=model,
        )
    except TranslationError:
        logger.exception("Translation failed; falling back to source text")
        return cleaned


async def translate_text(
    text: str,
    *,
    target_language: str,
    source_language: str,
    api_key: str | None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Translate a free-form letter or chat message RU↔IT."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if source_language == target_language:
        return cleaned
    result = await translate_fields_or_passthrough(
        {"message": cleaned},
        target_language=target_language,
        source_language=source_language,
        api_key=api_key,
        model=model,
    )
    return (result.get("message") or cleaned).strip()
