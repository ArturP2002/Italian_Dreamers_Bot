"""Telegram Mini App initData HMAC validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_session
from app.models import User


@dataclass(frozen=True)
class TelegramWebAppUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    is_premium: bool = False


@dataclass
class AuthContext:
    telegram: TelegramWebAppUser
    user: User
    is_admin: bool


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def validate_init_data(init_data: str, bot_token: str, *, max_age_seconds: int = 86400) -> dict:
    """Validate Telegram WebApp initData per official algorithm. Returns parsed fields."""
    if not init_data or not init_data.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing initData")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing hash")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    calculated = hmac.new(_secret_key(bot_token), check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid initData signature")

    auth_date_raw = data.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth_date") from exc
        if max_age_seconds > 0 and time.time() - auth_date > max_age_seconds:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="initData expired")

    return data


def parse_webapp_user(data: dict) -> TelegramWebAppUser:
    raw = data.get("user")
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user in initData")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user JSON") from exc
    if "id" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user id")
    return TelegramWebAppUser(
        id=int(payload["id"]),
        username=payload.get("username"),
        first_name=payload.get("first_name"),
        last_name=payload.get("last_name"),
        language_code=payload.get("language_code"),
        is_premium=bool(payload.get("is_premium", False)),
    )


async def upsert_user_from_telegram(
    session: AsyncSession,
    tg: TelegramWebAppUser,
    *,
    preferred_language: str | None = None,
) -> User:
    """Create or update user by telegram_id (safe under concurrent requests)."""
    lang = preferred_language or (tg.language_code if tg.language_code in {"ru", "it"} else "ru")
    values = {
        "telegram_id": tg.id,
        "telegram_username": tg.username,
        "telegram_first_name": tg.first_name,
        "telegram_last_name": tg.last_name,
        "language_code": lang[:2],
    }
    update_set: dict = {
        "telegram_username": tg.username,
        "telegram_first_name": tg.first_name,
        "telegram_last_name": tg.last_name,
    }
    if preferred_language is not None:
        update_set["language_code"] = lang[:2]

    stmt = (
        insert(User)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_=update_set,
        )
        .returning(User.id)
    )
    result = await session.execute(stmt)
    user_id = result.scalar_one()
    await session.commit()
    user = await session.get(User, user_id)
    assert user is not None
    return user


async def get_auth_context(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_telegram_id: str | None = Header(default=None, alias="X-Dev-Telegram-Id"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    if x_telegram_init_data:
        data = validate_init_data(x_telegram_init_data, settings.bot_token)
        tg = parse_webapp_user(data)
    elif settings.allow_dev_auth and x_dev_telegram_id:
        tg = TelegramWebAppUser(id=int(x_dev_telegram_id), first_name="Dev", language_code="ru")
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide X-Telegram-Init-Data header",
        )

    user = await upsert_user_from_telegram(session, tg)
    if user.is_blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is blocked")
    return AuthContext(telegram=tg, user=user, is_admin=settings.is_admin(tg.id))


async def require_admin(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not auth.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return auth
