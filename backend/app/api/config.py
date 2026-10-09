from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.services.telegram_api import get_bot_username

router = APIRouter(tags=["config"])


@router.get("/config")
async def public_config(settings: Settings = Depends(get_settings)) -> dict:
    """Public price/limit placeholders for Mini App UI (no secrets)."""
    bot_username = await get_bot_username(settings)
    return {
        "prices": {
            "message_credit_stars": settings.price_message_credit_stars,
            "message_pack_9_stars": settings.price_message_pack_9_stars,
            "message_pack_size": settings.message_pack_size,
            "profile_publish_stars": settings.price_profile_publish_stars,
            "ad_slot_stars": settings.price_ad_slot_stars,
        },
        "limits": {
            "contact_per_hour": settings.rate_contact_per_hour,
            "contact_per_day": settings.rate_contact_per_day,
            "max_pending_outgoing": settings.rate_max_pending_outgoing,
            "soft_ban_hours": settings.rate_soft_ban_hours,
        },
        "timezone": settings.app_timezone,
        "bot_username": bot_username,
    }
