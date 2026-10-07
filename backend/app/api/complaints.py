"""User complaints API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthContext, get_auth_context
from app.config import Settings, get_settings
from app.database import get_session
from app.services.complaints import ComplaintServiceError, create_complaint

router = APIRouter(prefix="/complaints", tags=["complaints"])


class ComplaintCreateBody(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
    message_request_id: int | None = None
    reported_user_id: int | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def file_complaint(
    body: ComplaintCreateBody,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        complaint = await create_complaint(
            session,
            settings,
            reporter=auth.user,
            reason=body.reason,
            message_request_id=body.message_request_id,
            reported_user_id=body.reported_user_id,
        )
    except ComplaintServiceError as exc:
        mapping = {
            "forbidden": status.HTTP_403_FORBIDDEN,
            "not_found": status.HTTP_404_NOT_FOUND,
        }
        raise HTTPException(
            status_code=mapping.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return {"ok": True, "id": complaint.id}
