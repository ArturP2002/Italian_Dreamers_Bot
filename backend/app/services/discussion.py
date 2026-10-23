"""Decide whether a discussion-group auto-forward should be deleted."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile, ProfileStatus
from app.services.publication_cache import cached_forward_action


async def should_delete_auto_forward(session: AsyncSession, channel_message_id: int) -> bool:
    cached = cached_forward_action(channel_message_id)
    if cached is not None:
        return cached

    result = await session.execute(
        select(Profile)
        .where(Profile.status == ProfileStatus.PUBLISHED.value)
        .order_by(Profile.published_at.desc())
        .limit(80)
    )
    for profile in result.scalars():
        splash = int(profile.splash_message_id) if profile.splash_message_id else None
        ids = {int(m) for m in (profile.channel_post_message_ids or []) if m}
        if splash:
            ids.add(splash)
        if splash and channel_message_id == splash:
            return False
        if channel_message_id in ids:
            return True
    return False
