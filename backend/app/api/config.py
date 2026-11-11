import time

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.services.telegram_api import get_bot_username, get_chat_member_count

router = APIRouter(tags=["config"])

_members_cache: dict[str, float | int | None] = {"count": None, "fetched_at": 0.0}
_MEMBERS_TTL_SEC = 600.0


async def _channel_member_count(settings: Settings) -> int:
    now = time.monotonic()
    cached = _members_cache.get("count")
    fetched_at = float(_members_cache.get("fetched_at") or 0)
    if cached is not None and now - fetched_at < _MEMBERS_TTL_SEC:
        return int(cached)

    live = await get_chat_member_count(settings, settings.channel_id)
    count = int(live) if live and live > 0 else settings.channel_members_fallback
    _members_cache["count"] = count
    _members_cache["fetched_at"] = now
    return count


@router.get("/config")
async def public_config(settings: Settings = Depends(get_settings)) -> dict:
    """Public price/limit placeholders for Mini App UI (no secrets)."""
    bot_username = await get_bot_username(settings)
    channel_members = await _channel_member_count(settings)
    return {
        "prices": {
            "message_credit_stars": settings.price_message_credit_stars,
            "message_pack_10_stars": settings.price_message_pack_10_stars,
            "message_credit_rub": settings.price_message_credit_rub,
            "message_pack_10_rub": settings.price_message_pack_10_rub,
            "message_pack_size": settings.message_pack_size,
            "profile_publish_stars": settings.price_profile_publish_stars,
            "profile_publish_rub": settings.price_profile_publish_rub,
            "ad_slot_stars": settings.price_ad_slot_stars,
            "unlimited_sub_stars": settings.price_unlimited_sub_stars,
            "unlimited_sub_rub": settings.price_unlimited_sub_rub,
            "catalog_top_stars": settings.price_catalog_top_stars,
            "catalog_top_rub": settings.price_catalog_top_rub,
        },
        "limits": {
            "contact_per_hour": settings.rate_contact_per_hour,
            "contact_per_day": settings.rate_contact_per_day,
            "max_pending_outgoing": settings.rate_max_pending_outgoing,
            "soft_ban_hours": settings.rate_soft_ban_hours,
        },
        "timezone": settings.app_timezone,
        "bot_username": bot_username,
        "channel_url": settings.channel_url,
        "channel_members": channel_members,
    }
