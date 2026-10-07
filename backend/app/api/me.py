from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth_context
from app.database import get_session
from app.models import LanguageCode, Profile

router = APIRouter(prefix="/me", tags=["me"])


class MeResponse(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    language_code: str
    gender: str | None
    message_credits: int
    is_admin: bool
    is_blocked: bool
    soft_ban_until: datetime | None
    is_soft_banned: bool
    profile_status: str | None
    profile_id: int | None


class LanguageUpdate(BaseModel):
    language_code: LanguageCode


class GenderUpdate(BaseModel):
    gender: str = Field(pattern="^(male|female)$")


async def _build_me(auth: AuthContext, session: AsyncSession) -> MeResponse:
    now = datetime.now(timezone.utc)
    soft_ban = auth.user.soft_ban_until
    is_soft_banned = bool(soft_ban and soft_ban > now)
    result = await session.execute(select(Profile).where(Profile.user_id == auth.user.id))
    profile = result.scalar_one_or_none()
    return MeResponse(
        id=auth.user.id,
        telegram_id=auth.user.telegram_id,
        username=auth.user.telegram_username,
        first_name=auth.user.telegram_first_name,
        language_code=auth.user.language_code,
        gender=auth.user.gender,
        message_credits=auth.user.message_credits,
        is_admin=auth.is_admin,
        is_blocked=auth.user.is_blocked,
        soft_ban_until=auth.user.soft_ban_until,
        is_soft_banned=is_soft_banned,
        profile_status=profile.status if profile else None,
        profile_id=profile.id if profile else None,
    )


@router.get("", response_model=MeResponse)
async def get_me(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    return await _build_me(auth, session)


@router.patch("/language", response_model=MeResponse)
async def update_language(
    body: LanguageUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    auth.user.language_code = body.language_code.value
    session.add(auth.user)
    await session.commit()
    await session.refresh(auth.user)
    return await _build_me(auth, session)


@router.patch("/gender", response_model=MeResponse)
async def update_gender(
    body: GenderUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    auth.user.gender = body.gender
    session.add(auth.user)
    await session.commit()
    await session.refresh(auth.user)
    return await _build_me(auth, session)
