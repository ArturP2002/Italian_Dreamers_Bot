"""Public Mini App catalog (queued + published). No usernames."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth_context
from app.config import Settings, get_settings
from app.database import get_session
from app.models import Profile, VerificationStatus
from app.services.catalog import (
    card_photos,
    default_catalog_gender,
    get_catalog_profile,
    list_catalog,
    localized_catalog_fields,
    written_profile_ids,
)
from app.services.channel import ensure_profile_translated
from app.services.entitlements import is_new_in_catalog, is_top_now
from app.services.likes import LikeServiceError, liked_profile_ids, matched_profile_ids, toggle_like
from app.services.profiles import get_user_profile

router = APIRouter(prefix="/catalog", tags=["catalog"])


class CatalogCard(BaseModel):
    id: int
    name: str
    age: int
    city: str
    country: str
    gender: str | None
    photo_urls: list[str]
    already_written: bool
    active_request_id: int | None = None
    verified: bool = False
    liked: bool = False
    matched: bool = False
    is_top: bool = False
    is_new: bool = False
    status: str
    blurred: bool = False


class CatalogPage(BaseModel):
    items: list[CatalogCard]
    next_cursor: str | None
    gender: str | None
    is_registered: bool = True
    free_remaining: int | None = None
    total_count: int | None = None
    gate_reached: bool = False


class CatalogProfileOut(CatalogCard):
    height_cm: int
    profession: str
    hobbies: str
    about: str
    desired_partner: str
    age_min: int
    age_max: int
    has_children: bool
    wants_children: str
    marital_status: str
    is_mine: bool
    published_at: datetime | None = None


def _viewer_lang(auth: AuthContext) -> str:
    code = (auth.user.language_code or "ru")[:2]
    return code if code in {"ru", "it"} else "ru"


def _card(
    profile: Profile,
    written: dict[int, int],
    *,
    liked: bool = False,
    matched: bool = False,
    fields: dict[str, str] | None = None,
    blurred: bool = False,
) -> CatalogCard:
    request_id = written.get(profile.id)
    loc = fields or {}
    name = loc.get("name") or profile.name
    city = loc.get("city") or profile.city
    if blurred:
        name = ""
        city = ""
    return CatalogCard(
        id=profile.id,
        name=name,
        age=0 if blurred else profile.age,
        city=city,
        country="" if blurred else (loc.get("country") or profile.country),
        gender=profile.gender,
        photo_urls=card_photos(profile),
        already_written=request_id is not None,
        active_request_id=request_id,
        verified=False if blurred else profile.verification_status == VerificationStatus.VERIFIED.value,
        liked=False if blurred else liked,
        matched=False if blurred else matched,
        is_top=False if blurred else is_top_now(profile),
        is_new=False if blurred else is_new_in_catalog(profile),
        status=profile.status,
        blurred=blurred,
    )


@router.get("/stats")
async def catalog_stats(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.services.catalog_gate import live_catalog_count, new_today_count, waiting_teaser_urls
    from app.services.registration import profile_is_registered

    own = await get_user_profile(session, auth.user.id)
    count = await live_catalog_count(session)
    today = await new_today_count(session)
    teasers = await waiting_teaser_urls(session, auth.user.gender or (own.gender if own else None))
    return {
        "total_count": count,
        "new_today_count": today,
        "is_registered": profile_is_registered(own),
        "teaser_photo_urls": teasers,
    }


@router.get("/newcomers")
async def catalog_newcomers(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.services.newcomers import list_today_newcomers

    profiles = await list_today_newcomers(session)
    ids = [p.id for p in profiles]
    written = await written_profile_ids(session, sender_id=auth.user.id, profile_ids=ids)
    lang = _viewer_lang(auth)
    items = [
        _card(p, written, fields=localized_catalog_fields(p, lang))
        for p in profiles
    ]
    return {"items": items}


@router.get("", response_model=CatalogPage)
async def catalog_feed(
    gender: str | None = Query(default=None),
    age_min: int | None = Query(default=None, ge=18, le=99),
    age_max: int | None = Query(default=None, ge=18, le=99),
    verified: bool = Query(default=False),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> CatalogPage:
    from app.services.catalog_gate import GUEST_DAILY_LIMIT, list_guest_catalog, live_catalog_count
    from app.services.registration import profile_is_registered

    own = await get_user_profile(session, auth.user.id)
    chosen = gender if gender in {"male", "female", "all"} else None
    if chosen is None:
        chosen = default_catalog_gender(auth.user, own)
    if chosen == "all":
        chosen = None
    registered = profile_is_registered(own)
    total = await live_catalog_count(session)
    lang = _viewer_lang(auth)

    if not registered:
        profiles, seen_today, free_remaining = await list_guest_catalog(
            session, viewer=auth.user, gender=chosen, limit=max(limit, GUEST_DAILY_LIMIT + 6)
        )
        written = await written_profile_ids(
            session, sender_id=auth.user.id, profile_ids=[p.id for p in profiles]
        )
        max_clear = min(GUEST_DAILY_LIMIT, seen_today)
        rebuilt = [
            _card(
                p,
                written,
                fields=None if idx >= max_clear else localized_catalog_fields(p, lang),
                blurred=idx >= max_clear,
            )
            for idx, p in enumerate(profiles)
        ]
        return CatalogPage(
            items=rebuilt,
            next_cursor=None,
            gender=chosen,
            is_registered=False,
            free_remaining=free_remaining,
            total_count=total,
            gate_reached=any(c.blurred for c in rebuilt) or free_remaining <= 0,
        )

    profiles, written, next_cursor = await list_catalog(
        session,
        viewer=auth.user,
        gender=chosen,
        age_min=age_min,
        age_max=age_max,
        verified=verified,
        cursor=cursor,
        limit=limit,
    )
    ids = [p.id for p in profiles]
    liked = await liked_profile_ids(session, auth.user.id, ids)
    matched = await matched_profile_ids(
        session,
        viewer_id=auth.user.id,
        viewer_profile_id=own.id if own else None,
        profile_ids=ids,
    )
    return CatalogPage(
        items=[
            _card(
                p,
                written,
                liked=p.id in liked,
                matched=p.id in matched,
                fields=localized_catalog_fields(p, lang),
            )
            for p in profiles
        ],
        next_cursor=next_cursor,
        gender=chosen,
        is_registered=True,
        total_count=total,
    )


@router.get("/{profile_id}", response_model=CatalogProfileOut)
async def catalog_detail(
    profile_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> CatalogProfileOut:
    profile = await get_catalog_profile(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    # Make sure opposite-audience translation exists (same cache as channel captions).
    await ensure_profile_translated(session, settings, profile)
    written = await written_profile_ids(session, sender_id=auth.user.id, profile_ids=[profile.id])
    liked = await liked_profile_ids(session, auth.user.id, [profile.id])
    own = await get_user_profile(session, auth.user.id)
    matched = await matched_profile_ids(
        session,
        viewer_id=auth.user.id,
        viewer_profile_id=own.id if own else None,
        profile_ids=[profile.id],
    )
    fields = localized_catalog_fields(profile, _viewer_lang(auth))
    card = _card(
        profile,
        written,
        liked=profile.id in liked,
        matched=profile.id in matched,
        fields=fields,
    )
    return CatalogProfileOut(
        **card.model_dump(),
        height_cm=profile.height_cm,
        profession=fields.get("profession") or profile.profession,
        hobbies=fields.get("hobbies") or profile.hobbies,
        about=fields.get("about") or profile.about,
        desired_partner=fields.get("desired_partner") or profile.desired_partner,
        age_min=profile.age_min,
        age_max=profile.age_max,
        has_children=profile.has_children,
        wants_children=profile.wants_children,
        marital_status=profile.marital_status,
        is_mine=profile.user_id == auth.user.id,
        published_at=profile.published_at,
    )


@router.post("/{profile_id}/like")
async def like_catalog_profile(
    profile_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    from app.services.registration import profile_is_registered

    own = await get_user_profile(session, auth.user.id)
    if not profile_is_registered(own):
        raise HTTPException(status_code=403, detail="registration_required")
    profile = await get_catalog_profile(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        return await toggle_like(session, settings, actor=auth.user, profile=profile)
    except LikeServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc
