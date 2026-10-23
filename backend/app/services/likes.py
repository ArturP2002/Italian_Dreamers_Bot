"""Catalog likes and mutual match."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import Like, Profile, User
from app.services.catalog import CATALOG_STATUSES, card_photos
from app.services.notify import notify_match
from app.services.profiles import get_user_profile


class LikeServiceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def liked_profile_ids(session: AsyncSession, user_id: int, profile_ids: list[int]) -> set[int]:
    if not profile_ids:
        return set()
    result = await session.execute(
        select(Like.profile_id).where(Like.from_user_id == user_id, Like.profile_id.in_(profile_ids))
    )
    return {int(row[0]) for row in result.all()}


async def matched_profile_ids(
    session: AsyncSession,
    *,
    viewer_id: int,
    viewer_profile_id: int | None,
    profile_ids: list[int],
) -> set[int]:
    if not profile_ids or viewer_profile_id is None:
        return set()
    owners = await session.execute(select(Profile.id, Profile.user_id).where(Profile.id.in_(profile_ids)))
    owner_by_profile = {int(pid): int(uid) for pid, uid in owners.all()}
    owner_ids = list(owner_by_profile.values())
    if not owner_ids:
        return set()
    back = await session.execute(
        select(Like.from_user_id).where(
            Like.profile_id == viewer_profile_id,
            Like.from_user_id.in_(owner_ids),
        )
    )
    owners_who_liked_me = {int(row[0]) for row in back.all()}
    return {pid for pid, uid in owner_by_profile.items() if uid in owners_who_liked_me}


async def toggle_like(
    session: AsyncSession,
    settings: Settings,
    *,
    actor: User,
    profile: Profile,
) -> dict:
    if profile.user_id == actor.id:
        raise LikeServiceError("own_profile", "Cannot like your own profile")
    if profile.status not in CATALOG_STATUSES:
        raise LikeServiceError("not_in_catalog", "Profile is not in catalog")

    existing = await session.execute(
        select(Like).where(Like.from_user_id == actor.id, Like.profile_id == profile.id)
    )
    like = existing.scalar_one_or_none()
    if like is not None:
        await session.delete(like)
        await session.commit()
        return {"liked": False, "matched": False}

    now = datetime.now(timezone.utc)
    like = Like(from_user_id=actor.id, profile_id=profile.id)
    viewer_profile = await get_user_profile(session, actor.id)
    matched = False
    if viewer_profile is not None:
        back = await session.execute(
            select(Like).where(Like.from_user_id == profile.user_id, Like.profile_id == viewer_profile.id)
        )
        counterpart = back.scalar_one_or_none()
        if counterpart is not None:
            matched = True
            like.matched_at = now
            counterpart.matched_at = counterpart.matched_at or now
            session.add(counterpart)
    session.add(like)
    await session.commit()

    if matched:
        owner_result = await session.execute(select(User).where(User.id == profile.user_id))
        owner = owner_result.scalar_one_or_none()
        if owner is not None:
            await notify_match(settings, a=actor, b=owner, liked_profile=profile, viewer_profile=viewer_profile)
    return {"liked": True, "matched": matched}


async def list_sent_likes(session: AsyncSession, user_id: int) -> list[tuple[Like, Profile]]:
    result = await session.execute(
        select(Like, Profile)
        .join(Profile, Profile.id == Like.profile_id)
        .where(Like.from_user_id == user_id, Profile.status.in_(list(CATALOG_STATUSES)))
        .options(selectinload(Profile.photos))
        .order_by(Like.created_at.desc())
        .limit(100)
    )
    return [(like, profile) for like, profile in result.all()]


async def list_received_likes(session: AsyncSession, user_id: int) -> list[tuple[Like, Profile | None, User]]:
    own = await get_user_profile(session, user_id)
    if own is None:
        return []
    result = await session.execute(
        select(Like, User)
        .join(User, User.id == Like.from_user_id)
        .where(Like.profile_id == own.id)
        .order_by(Like.created_at.desc())
        .limit(100)
    )
    rows = list(result.all())
    sender_ids = [user.id for _, user in rows]
    profiles_by_user: dict[int, Profile] = {}
    if sender_ids:
        pres = await session.execute(
            select(Profile)
            .where(Profile.user_id.in_(sender_ids), Profile.status.in_(list(CATALOG_STATUSES)))
            .options(selectinload(Profile.photos))
        )
        for profile in pres.scalars().all():
            profiles_by_user[profile.user_id] = profile
    return [(like, profiles_by_user.get(user.id), user) for like, user in rows]


def like_card(profile: Profile, *, liked: bool, matched: bool) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "age": profile.age,
        "city": profile.city,
        "photo_urls": card_photos(profile),
        "verified": profile.verification_status == "verified",
        "liked": liked,
        "matched": matched,
        "status": profile.status,
    }
