from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth_context
from app.database import get_session
from app.services.likes import (
    like_card,
    liked_profile_ids,
    list_received_likes,
    list_sent_likes,
    matched_profile_ids,
)
from app.services.profiles import get_user_profile
from app.services.registration import profile_is_registered

router = APIRouter(prefix="/likes", tags=["likes"])


@router.get("")
async def my_likes(
    kind: str = Query(default="sent"),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    own = await get_user_profile(session, auth.user.id)
    if not profile_is_registered(own):
        raise HTTPException(status_code=403, detail="registration_required")
    own_id = own.id if own else None
    if kind == "received":
        rows = await list_received_likes(session, auth.user.id)
        sender_profile_ids = [sp.id for _, sp, _ in rows if sp is not None]
        i_liked = await liked_profile_ids(session, auth.user.id, sender_profile_ids)
        items = []
        for _like, sender_profile, user in rows:
            if sender_profile is None:
                items.append(
                    {
                        "id": None,
                        "name": user.telegram_first_name or "—",
                        "age": None,
                        "city": "",
                        "photo_urls": [],
                        "verified": False,
                        "liked": False,
                        "matched": False,
                        "status": None,
                    }
                )
            else:
                # Received list = they already liked me; mutual only if I liked back.
                liked_back = sender_profile.id in i_liked
                items.append(
                    like_card(
                        sender_profile,
                        liked=liked_back,
                        matched=liked_back,
                    )
                )
        return {"kind": "received", "items": items}

    rows = await list_sent_likes(session, auth.user.id)
    matched = await matched_profile_ids(
        session,
        viewer_id=auth.user.id,
        viewer_profile_id=own_id,
        profile_ids=[p.id for _, p in rows],
    )
    items = [like_card(profile, liked=True, matched=profile.id in matched) for _, profile in rows]
    return {"kind": "sent", "items": items}
