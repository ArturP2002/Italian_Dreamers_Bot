"""Subscription renewal reminders + one-shot credits-cut notices."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select

from app.config import Settings
from app.database import async_session_factory
from app.models import Subscription, SubscriptionStatus, User
from app.services.entitlements import utcnow
from app.services.telegram_api import send_message

logger = logging.getLogger(__name__)


async def process_subscription_renewal_reminders(settings: Settings) -> int:
    """Remind ~2 days before expires_at for active (auto-renewing) subscriptions."""
    now = utcnow()
    window_start = now + timedelta(days=1, hours=12)
    window_end = now + timedelta(days=2, hours=12)
    sent = 0
    async with async_session_factory() as session:
        result = await session.execute(
            select(Subscription)
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE.value,
                Subscription.expires_at >= window_start,
                Subscription.expires_at <= window_end,
                Subscription.renewal_reminded_at.is_(None),
            )
            .limit(80)
        )
        subs = list(result.scalars().all())
        if not subs:
            return 0
        user_ids = [s.user_id for s in subs]
        users = {
            u.id: u
            for u in (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars()
        }
        for sub in subs:
            user = users.get(sub.user_id)
            if user is None:
                continue
            lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
            until = sub.expires_at.strftime("%d.%m.%Y")
            if lang == "it":
                text = (
                    f"⏰ Dreamers Plus si rinnova tra circa 2 giorni (fino al <b>{until}</b>). "
                    "Se non vuoi il rinnovo, annulla in «Il mio abbonamento»."
                )
            else:
                text = (
                    f"⏰ Dreamers Plus продлится примерно через 2 дня (до <b>{until}</b>). "
                    "Если не нужно — отмените в «Моя подписка»."
                )
            try:
                await send_message(settings, user.telegram_id, text)
                sub.renewal_reminded_at = now
                session.add(sub)
                sent += 1
            except Exception:
                logger.exception("Renewal remind failed for user %s", user.telegram_id)
        await session.commit()
    return sent


async def notify_credits_cut_once(settings: Settings) -> int:
    """Hard cut: warn users who still have message_credits > 0 (once)."""
    sent = 0
    async with async_session_factory() as session:
        result = await session.execute(
            select(User)
            .where(
                User.message_credits > 0,
                User.credits_cut_notified_at.is_(None),
                User.is_blocked.is_(False),
            )
            .limit(100)
        )
        users = list(result.scalars().all())
        now = utcnow()
        for user in users:
            lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
            if lang == "it":
                text = (
                    "ℹ️ I crediti per le lettere non sono più in uso. "
                    "Per scrivere e leggere serve <b>Dreamers Plus</b> "
                    "(20 € / 2000 ₽ / 1000 ★ al mese)."
                )
            else:
                text = (
                    "ℹ️ Кредиты на знакомства больше не действуют. "
                    "Чтобы писать и читать, нужен <b>Dreamers Plus</b> "
                    "(20 € / 2000 ₽ / 1000 ★ в месяц)."
                )
            try:
                await send_message(settings, user.telegram_id, text)
                user.credits_cut_notified_at = now
                session.add(user)
                sent += 1
            except Exception:
                logger.exception("Credits-cut notify failed %s", user.telegram_id)
        await session.commit()
    return sent
