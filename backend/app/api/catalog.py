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
    written_profile_ids,
)
from app.services.entitlements import is_top_now
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
    status: str


class CatalogPage(BaseModel):
    items: list[CatalogCard]
    next_cursor: str | None
    gender: str | None


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


def _card(
    profile: Profile,
    written: dict[int, int],
    *,
    liked: bool = False,
    matched: bool = False,
) -> CatalogCard:
    request_id = written.get(profile.id)
    return CatalogCard(
        id=profile.id,
        name=profile.name,
        age=profile.age,
        city=profile.city,
        country=profile.country,
        gender=profile.gender,
        photo_urls=card_photos(profile),
        already_written=request_id is not None,
        active_request_id=request_id,
        verified=profile.verification_status == VerificationStatus.VERIFIED.value,
        liked=liked,
        matched=matched,
        is_top=is_top_now(profile),
        status=profile.status,
    )


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
    own = await get_user_profile(session, auth.user.id)
    chosen = gender if gender in {"male", "female", "all"} else None
    if chosen is None:
        chosen = default_catalog_gender(auth.user, own)
    if chosen == "all":
        chosen = None
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
        items=[_card(p, written, liked=p.id in liked, matched=p.id in matched) for p in profiles],
        next_cursor=next_cursor,
        gender=chosen,
    )


@router.get("/{profile_id}", response_model=CatalogProfileOut)
async def catalog_detail(
    profile_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> CatalogProfileOut:
    profile = await get_catalog_profile(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    written = await written_profile_ids(session, sender_id=auth.user.id, profile_ids=[profile.id])
    liked = await liked_profile_ids(session, auth.user.id, [profile.id])
    own = await get_user_profile(session, auth.user.id)
    matched = await matched_profile_ids(
        session,
        viewer_id=auth.user.id,
        viewer_profile_id=own.id if own else None,
        profile_ids=[profile.id],
    )
    card = _card(profile, written, liked=profile.id in liked, matched=profile.id in matched)
    return CatalogProfileOut(
        **card.model_dump(),
        height_cm=profile.height_cm,
        profession=profile.profession,
        hobbies=profile.hobbies,
        about=profile.about,
        desired_partner=profile.desired_partner,
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
    profile = await get_catalog_profile(session, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    try:
        return await toggle_like(session, settings, actor=auth.user, profile=profile)
    except LikeServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc
