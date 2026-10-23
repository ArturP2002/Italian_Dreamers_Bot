"""Short-lived map of just-published channel posts (race with discussion auto-forward)."""

from __future__ import annotations

import time

from app.models import Profile

# channel_message_id -> (expires_at, is_splash)
_RECENT: dict[int, tuple[float, bool]] = {}
TTL_SECONDS = 600.0


def remember_publication(profile: Profile) -> None:
    splash = int(profile.splash_message_id) if profile.splash_message_id else None
    ids = [int(m) for m in (profile.channel_post_message_ids or []) if m]
    if not ids and splash:
        ids = [splash]
    expires = time.time() + TTL_SECONDS
    for message_id in ids:
        _RECENT[message_id] = (expires, splash is not None and message_id == splash)
    _prune()


def cached_forward_action(channel_message_id: int) -> bool | None:
    """True = delete copy, False = keep (splash), None = look up DB."""
    hit = _RECENT.get(channel_message_id)
    if hit is None:
        return None
    expires, is_splash = hit
    if expires < time.time():
        _RECENT.pop(channel_message_id, None)
        return None
    return False if is_splash else True


def _prune() -> None:
    now = time.time()
    dead = [key for key, (expires, _) in _RECENT.items() if expires < now]
    for key in dead:
        _RECENT.pop(key, None)


def reset_cache() -> None:
    _RECENT.clear()
