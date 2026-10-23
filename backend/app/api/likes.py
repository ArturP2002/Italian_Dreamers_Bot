from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth_context
from app.database import get_session
from app.services.likes import like_card, list_received_likes, list_sent_likes
from app.services.profiles import get_user_profile

router = APIRouter(prefix="/likes", tags=["likes"])


@router.get("")
async def my_likes(
    kind: str = Query(default="sent"),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    own = await get_user_profile(session, auth.user.id)
    own_id = own.id if own else None
    if kind == "received":
        rows = await list_received_likes(session, auth.user.id)
        items = []
        for like, sender_profile, user in rows:
            if sender_profile is None:
                items.append(
                    {
                        "id": None,
                        "name": user.telegram_first_name or "—",
                        "age": None,
                        "city": "",
                        "photo_urls": [],
                        "verified": False,
                        "liked": True,
                        "matched": like.matched_at is not None,
                        "status": None,
                    }
                )
            else:
                items.append(
                    like_card(
                        sender_profile,
                        liked=True,
                        matched=like.matched_at is not None,
                    )
                )
        return {"kind": "received", "items": items}

    rows = await list_sent_likes(session, auth.user.id)
    from app.services.likes import matched_profile_ids

    matched = await matched_profile_ids(
        session,
        viewer_id=auth.user.id,
        viewer_profile_id=own_id,
        profile_ids=[p.id for _, p in rows],
    )
    items = [like_card(profile, liked=True, matched=profile.id in matched) for _, profile in rows]
    return {"kind": "sent", "items": items}
