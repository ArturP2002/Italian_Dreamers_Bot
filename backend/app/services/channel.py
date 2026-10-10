"""Channel caption + publish (splash → profile album + Write button)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.config import Settings
from app.models import Gender, MaritalStatus, Profile, ProfileStatus, WantsChildren
from app.services.splash import (
    audience_language_for_profile,
    build_splash_image,
    resolve_cover_texts,
)
from app.services.greeting_video import video_path
from app.services.telegram_api import (
    TelegramApiError,
    bot_has_main_web_app,
    send_media_album,
    send_message,
    send_photo_file,
    send_photo_media,
)
from app.services.translate import translate_fields_or_passthrough

logger = logging.getLogger(__name__)

MEDIA_PROFILES = Path(__file__).resolve().parents[2] / "media" / "profiles"

CAPTION_LIMIT = 1024
TEXT_LIMIT = 4096
MAX_ALBUM_PHOTOS = 10

CAPTION_I18N = {
    "ru": {
        "years": "лет",
        "height": "Рост",
        "marital": "Семейное положение",
        "children": "Дети",
        "wants_children": "Хочет ещё",
        "looking_for": "Ищет",
        "yes": "Да",
        "no": "Нет",
        "unsure": "Не уверен(а)",
        "single": "Холост / не замужем",
        "divorced": "Разведён(а)",
        "write": "💌 Написать",
        "write_prompt": "💌 Понравилась анкета? Напишите письмо через бота 👇",
    },
    "it": {
        "years": "anni",
        "height": "Altezza",
        "marital": "Stato civile",
        "children": "Figli",
        "wants_children": "Ne vorrebbe altri",
        "looking_for": "Cerca",
        "yes": "Sì",
        "no": "No",
        "unsure": "Non so",
        "single": "Celibe / nubile",
        "divorced": "Divorziato/a",
        "write": "💌 Scrivi",
        "write_prompt": "💌 Ti piace questo profilo? Scrivi una lettera tramite il bot 👇",
    },
}


def source_language_for_profile(profile: Profile) -> str:
    if profile.gender == Gender.MALE.value:
        return "it"
    return "ru"


def build_channel_caption(profile: Profile, language: str, fields: dict[str, str] | None = None) -> str:
    """Public caption as plain text (escape before sending with HTML parse mode).

    age_min/age_max intentionally omitted.
    """
    t = CAPTION_I18N.get(language, CAPTION_I18N["it"])
    f = fields or {}
    name = f.get("name", profile.name)
    city = f.get("city", profile.city)
    country = f.get("country", profile.country)
    profession = f.get("profession", profile.profession)
    about = f.get("about", profile.about)
    desired = f.get("desired_partner", profile.desired_partner)

    children = t["yes"] if profile.has_children else t["no"]
    wants_key = {
        WantsChildren.YES.value: "yes",
        WantsChildren.NO.value: "no",
        WantsChildren.UNSURE.value: "unsure",
    }.get(profile.wants_children, "unsure")
    marital_key = {
        MaritalStatus.SINGLE.value: "single",
        MaritalStatus.DIVORCED.value: "divorced",
    }.get(profile.marital_status, "single")

    emoji = "💃" if profile.gender != Gender.MALE.value else "🕺"
    return (
        f"{emoji} {name}, {profile.age} {t['years']}\n"
        f"📍 {city}, {country}\n"
        f"📏 {t['height']}: {profile.height_cm} cm\n"
        f"💍 {t['marital']}: {t[marital_key]}\n"
        f"👶 {t['children']}: {children} · {t['wants_children']}: {t[wants_key]}\n"
        f"💼 {profession}\n\n"
        f"{about}\n\n"
        f"💭 {t['looking_for']}: {desired}"
    )


def _bot_startapp_url(
    bot_username: str | None,
    profile_id: int,
    settings: Settings,
    language: str,
    *,
    has_main_web_app: bool = False,
) -> dict:
    t = CAPTION_I18N.get(language, CAPTION_I18N["it"])
    if bot_username and has_main_web_app:
        link = f"https://t.me/{bot_username}?startapp=write_{profile_id}"
    elif bot_username:
        # Without a Main Mini App in BotFather, ?startapp only opens the chat;
        # ?start reaches /start and the bot replies with a web_app button.
        link = f"https://t.me/{bot_username}?start=write_{profile_id}"
    else:
        # Fallback for local/dev without getMe username
        link = f"{settings.webapp_url.rstrip('/')}?startapp=write_{profile_id}"
    return {"inline_keyboard": [[{"text": t["write"], "url": link}]]}


async def ensure_profile_translated(
    session: AsyncSession,
    settings: Settings,
    profile: Profile,
) -> dict[str, str]:
    target = audience_language_for_profile(profile.gender)
    source = source_language_for_profile(profile)

    cached = {
        "name": profile.name_translated,
        "city": profile.city_translated,
        "country": profile.country_translated,
        "profession": profile.profession_translated,
        "about": profile.about_translated,
        "desired_partner": profile.desired_partner_translated,
        "cover_answer": profile.cover_answer_translated,
    }
    if profile.translated_language == target and all(
        cached[k] for k in ("name", "city", "country", "profession", "about", "desired_partner")
    ):
        return {k: v for k, v in cached.items() if v}

    source_fields = {
        "name": profile.name,
        "city": profile.city,
        "country": profile.country,
        "profession": profile.profession,
        "about": profile.about,
        "desired_partner": profile.desired_partner,
        "cover_answer": profile.cover_answer or "",
    }
    translated = await translate_fields_or_passthrough(
        source_fields,
        target_language=target,
        source_language=source,
        api_key=settings.translation_api_key,
        model=settings.openai_translate_model,
    )
    profile.name_translated = translated.get("name")
    profile.city_translated = translated.get("city")
    profile.country_translated = translated.get("country")
    profile.profession_translated = translated.get("profession")
    profile.about_translated = translated.get("about")
    profile.desired_partner_translated = translated.get("desired_partner")
    profile.cover_answer_translated = (translated.get("cover_answer") or "")[:70] or None
    profile.translated_language = target
    profile.translated_at = datetime.now(timezone.utc)
    session.add(profile)
    await session.commit()
    return translated


def _local_photo_path(file_id: str) -> Path | None:
    if file_id.startswith("local:"):
        path = MEDIA_PROFILES / file_id.removeprefix("local:")
        return path if path.exists() else None
    return None


def _photo_source(file_id: str) -> str | Path:
    if file_id.startswith("local:"):
        path = _local_photo_path(file_id)
        if path is None:
            raise ValueError(f"Photo file is missing: {file_id}")
        return path
    return file_id


def _tg_len(text: str) -> int:
    """Telegram measures text limits in UTF-16 code units (emoji count as 2)."""
    return len(text.encode("utf-16-le")) // 2


def _truncate(text: str, limit: int) -> str:
    if _tg_len(text) <= limit:
        return text
    out = text
    while out and _tg_len(out) > limit - 1:
        out = out[:-1]
    return out.rstrip() + "…"


async def publish_profile_to_channel(
    session: AsyncSession,
    settings: Settings,
    profile_id: int,
    *,
    bot_username: str | None = None,
) -> Profile:
    result = await session.execute(
        select(Profile)
        .where(Profile.id == profile_id)
        .options(selectinload(Profile.photos), selectinload(Profile.user))
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise ValueError("Profile not found")
    if profile.status not in {
        ProfileStatus.QUEUED.value,
        ProfileStatus.APPROVED.value,
        ProfileStatus.AWAITING_PAYMENT.value,
    } and profile.status != ProfileStatus.PUBLISHED.value:
        # Allow re-publish only from queued primarily
        if profile.status != ProfileStatus.QUEUED.value:
            raise ValueError(f"Cannot publish profile in status {profile.status}")

    if not settings.channel_id:
        raise ValueError("CHANNEL_ID is not configured")

    fields = await ensure_profile_translated(session, settings, profile)
    language = audience_language_for_profile(profile.gender)
    _, pronoun, question, answer = resolve_cover_texts(
        gender=profile.gender,
        cover_question_id=profile.cover_question_id,
        cover_answer=profile.cover_answer or "",
        cover_answer_translated=fields.get("cover_answer") or profile.cover_answer_translated,
    )
    splash_path = build_splash_image(
        question=question,
        answer=answer,
        pronoun=pronoun,
        profile_id=profile.id,
    )

    splash_resp = await send_photo_file(settings, settings.channel_id, splash_path)
    splash_message_id = (splash_resp.get("result") or {}).get("message_id")

    greeting_video = video_path(profile.greeting_video_file_id)
    photo_limit = MAX_ALBUM_PHOTOS - (1 if greeting_video else 0)
    photos = sorted(profile.photos or [], key=lambda p: p.position)[:photo_limit]
    caption = build_channel_caption(profile, language, fields)
    has_main_web_app = await bot_has_main_web_app(settings) if bot_username else False
    markup = _bot_startapp_url(
        bot_username, profile.id, settings, language, has_main_web_app=has_main_web_app
    )
    t = CAPTION_I18N.get(language, CAPTION_I18N["it"])

    channel_message_id: int | None = None
    # Telegram albums cannot carry inline keyboards, so the Write button always
    # goes into a separate text post: the full profile text when it does not fit
    # into the album caption, otherwise a short call to action.
    caption_fits = _tg_len(caption) <= CAPTION_LIMIT
    full_text = escape(_truncate(caption, TEXT_LIMIT), quote=False)

    if not photos:
        msg = await send_message(
            settings,
            settings.channel_id,
            full_text,
            reply_markup=markup,
            disable_link_preview=True,
        )
        channel_message_id = (msg.get("result") or {}).get("message_id")
    else:
        album_caption = escape(caption, quote=False) if caption_fits else None
        photo_items: list[tuple[str, str | Path]] = [
            ("photo", _photo_source(p.file_id)) for p in photos
        ]
        items = ([("video", greeting_video)] if greeting_video else []) + photo_items
        if len(items) == 1:
            source = items[0][1]
            if isinstance(source, Path):
                resp = await send_photo_file(settings, settings.channel_id, source, caption=album_caption)
            else:
                resp = await send_photo_media(settings, settings.channel_id, source, caption=album_caption)
            channel_message_id = (resp.get("result") or {}).get("message_id")
        else:
            try:
                group = await send_media_album(
                    settings, settings.channel_id, items, caption=album_caption
                )
            except TelegramApiError:
                if not greeting_video:
                    raise
                logger.exception("Album with greeting video failed for profile %s; retrying without it", profile.id)
                group = await send_media_album(
                    settings, settings.channel_id, photo_items, caption=album_caption
                )
            results = group.get("result") or []
            if results:
                channel_message_id = results[0].get("message_id")

        await send_message(
            settings,
            settings.channel_id,
            t["write_prompt"] if caption_fits else full_text,
            reply_markup=markup,
            disable_link_preview=True,
        )

    profile.status = ProfileStatus.PUBLISHED.value
    profile.published_at = datetime.now(timezone.utc)
    profile.splash_message_id = splash_message_id
    profile.channel_message_id = channel_message_id
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile
