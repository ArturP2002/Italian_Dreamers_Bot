"""Block contact details in first-contact / letter text (phones, @handles, links)."""

from __future__ import annotations

import re

_PHONE_RE = re.compile(
    r"(?:\+|00)?\d[\d\s\-().]{7,}\d",
    re.UNICODE,
)
_USERNAME_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{4,}", re.UNICODE)
_URL_RE = re.compile(
    r"(?:https?://|www\.|t\.me/|telegram\.me/)[^\s]+",
    re.IGNORECASE,
)
_DOT_DOMAIN_RE = re.compile(
    r"\b[a-z0-9][a-z0-9\-]*\.(?:com|ru|it|org|net|io|me|co|info)\b",
    re.IGNORECASE,
)


def contains_contact_info(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if _URL_RE.search(value):
        return True
    if _USERNAME_RE.search(value):
        return True
    if _DOT_DOMAIN_RE.search(value):
        return True
    if _PHONE_RE.search(value):
        digits = re.sub(r"\D", "", value)
        # Avoid false positives on ages/years alone; require enough digit density
        if len(digits) >= 8:
            return True
    return False
