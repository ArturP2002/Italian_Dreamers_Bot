"""User Mini App API: advertising requests."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth_context
from app.config import Settings, get_settings
from app.database import get_session
from app.models import AdRequestStatus
from app.services.ads import (
    AdServiceError,
    create_ad_request,
    get_ad,
    list_ads,
)
from app.services.payments import create_ad_payment, send_ad_invoice

router = APIRouter(prefix="/ads", tags=["ads"])


class AdCreateBody(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    category: str = Field(default="other", max_length=64)
    body: str = Field(min_length=10, max_length=2000)
    contact: str | None = Field(default=None, max_length=255)
    desired_date: str | None = Field(default=None, max_length=64)


class AdOut(BaseModel):
    id: int
    status: str
    title: str
    category: str
    body: str
    contact: str | None
    desired_date: str | None
    moderation_feedback: str | None
    paid_at: datetime | None
    scheduled_at: datetime | None
    activated_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    can_pay: bool


def _out(ad) -> AdOut:
    return AdOut(
        id=ad.id,
        status=ad.status,
        title=ad.title,
        category=ad.category,
        body=ad.body,
        contact=ad.contact,
        desired_date=ad.desired_date,
        moderation_feedback=ad.moderation_feedback,
        paid_at=ad.paid_at,
        scheduled_at=ad.scheduled_at,
        activated_at=ad.activated_at,
        expires_at=ad.expires_at,
        created_at=ad.created_at,
        can_pay=ad.status == AdRequestStatus.AWAITING_PAYMENT.value,
    )


@router.get("/mine", response_model=list[AdOut])
async def my_ads(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> list[AdOut]:
    ads = await list_ads(session, user_id=auth.user.id, limit=30)
    return [_out(a) for a in ads]


@router.post("", response_model=AdOut, status_code=status.HTTP_201_CREATED)
async def submit_ad(
    body: AdCreateBody,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AdOut:
    try:
        ad = await create_ad_request(
            session,
            settings,
            user=auth.user,
            title=body.title,
            category=body.category,
            body=body.body,
            contact=body.contact,
            desired_date=body.desired_date,
        )
    except AdServiceError as exc:
        code = status.HTTP_403_FORBIDDEN if exc.code == "blocked" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail={"code": exc.code, "message": exc.message}) from exc
    return _out(ad)


@router.post("/{ad_id}/pay")
async def pay_ad(
    ad_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    ad = await get_ad(session, ad_id)
    if ad is None or ad.user_id != auth.user.id:
        raise HTTPException(status_code=404, detail="Ad not found")
    if ad.status != AdRequestStatus.AWAITING_PAYMENT.value:
        raise HTTPException(status_code=409, detail="Ad is not awaiting payment")
    payment = await create_ad_payment(session, settings, user=auth.user, ad=ad)
    await send_ad_invoice(settings, user=auth.user, ad=ad, payment=payment)
    return {"ok": True, "stars": payment.stars_amount}
