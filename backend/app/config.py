"""
Italy Dreamers — FastAPI backend (Phase 0 scaffold).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(alias="BOT_TOKEN", default="0000000000:DEV_PLACEHOLDER")
    admin_telegram_ids: str = Field(alias="ADMIN_TELEGRAM_IDS", default="")
    database_url: str = Field(
        alias="DATABASE_URL",
        default="postgresql+asyncpg://dreamers:dreamers@localhost:5432/dreamers",
    )
    channel_id: int = Field(alias="CHANNEL_ID", default=0)
    channel_url: str = Field(alias="CHANNEL_URL", default="https://t.me/italiandreamers")
    discussion_chat_id: int = Field(alias="DISCUSSION_CHAT_ID", default=0)
    webapp_url: str = Field(alias="WEBAPP_URL", default="http://localhost:5173")
    cors_origins: str = Field(alias="CORS_ORIGINS", default="http://localhost:5173")

    log_level: str = Field(alias="LOG_LEVEL", default="INFO")
    environment: str = Field(alias="ENVIRONMENT", default="development")
    app_timezone: str = Field(alias="APP_TIMEZONE", default="Europe/Rome")

    # Prices (Stars)
    price_message_credit_stars: int = Field(alias="PRICE_MESSAGE_CREDIT_STARS", default=100)
    # The old variable name is still accepted so a not-yet-updated .env keeps working.
    price_message_pack_10_stars: int = Field(
        validation_alias=AliasChoices("PRICE_MESSAGE_PACK_10_STARS", "PRICE_MESSAGE_PACK_9_STARS"),
        default=500,
    )
    message_pack_size: int = Field(alias="MESSAGE_PACK_SIZE", default=10)
    referral_bonus_credits: int = Field(alias="REFERRAL_BONUS_CREDITS", default=1)
    price_profile_publish_stars: int = Field(alias="PRICE_PROFILE_PUBLISH_STARS", default=1000)
    price_ad_slot_stars: int = Field(alias="PRICE_AD_SLOT_STARS", default=1000)
    price_unlimited_sub_stars: int = Field(alias="PRICE_UNLIMITED_SUB_STARS", default=1000)
    price_catalog_top_stars: int = Field(alias="PRICE_CATALOG_TOP_STARS", default=1000)
    # Telegram Stars recurring period (seconds). Bot API currently allows 2592000 = 30 days.
    subscription_period_seconds: int = Field(alias="SUBSCRIPTION_PERIOD_SECONDS", default=2592000)
    # Reserved for YooKassa later — unused in this wave.
    price_message_credit_rub: int = Field(alias="PRICE_MESSAGE_CREDIT_RUB", default=0)
    price_message_pack_10_rub: int = Field(alias="PRICE_MESSAGE_PACK_10_RUB", default=0)
    price_profile_publish_rub: int = Field(alias="PRICE_PROFILE_PUBLISH_RUB", default=0)
    price_ad_slot_rub: int = Field(alias="PRICE_AD_SLOT_RUB", default=0)
    price_unlimited_sub_rub: int = Field(alias="PRICE_UNLIMITED_SUB_RUB", default=0)
    price_catalog_top_rub: int = Field(alias="PRICE_CATALOG_TOP_RUB", default=0)

    # Telegram username (without @) shown by /support and /paysupport.
    support_username: str = Field(alias="SUPPORT_USERNAME", default="")

    # Channel publication slots (Rome time). Ads stay at 10:00, so default times skip 10:00.
    slot_per_gender_per_day: int = Field(alias="SLOT_PER_GENDER_PER_DAY", default=5)
    slot_times: str = Field(
        alias="SLOT_TIMES",
        default="09:00,11:00,12:00,13:00,14:00,15:00,16:00,17:00,18:00,20:00",
    )

    # Rate limits
    rate_contact_per_hour: int = Field(alias="RATE_CONTACT_PER_HOUR", default=50)
    rate_contact_per_day: int = Field(alias="RATE_CONTACT_PER_DAY", default=100)
    rate_max_pending_outgoing: int = Field(alias="RATE_MAX_PENDING_OUTGOING", default=0)
    rate_soft_ban_hours: int = Field(alias="RATE_SOFT_BAN_HOURS", default=0)

    # Dev: skip Telegram HMAC when initData absent (local browser only)
    allow_dev_auth: bool = Field(alias="ALLOW_DEV_AUTH", default=False)

    # Translation (OpenAI gpt-4o-mini)
    openai_api_key: str | None = Field(alias="OPENAI_API_KEY", default=None)
    openai_translate_model: str = Field(alias="OPENAI_TRANSLATE_MODEL", default="gpt-4o-mini")
    openai_vision_model: str = Field(alias="OPENAI_VISION_MODEL", default="gpt-4o-mini")

    @property
    def translation_api_key(self) -> str | None:
        key = (self.openai_api_key or "").strip()
        return key or None

    @property
    def admin_ids(self) -> frozenset[int]:
        raw = self.admin_telegram_ids.strip()
        if not raw:
            return frozenset()
        return frozenset(int(part.strip()) for part in raw.split(",") if part.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self.admin_ids


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
