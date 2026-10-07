"""Telegram Stars payment handlers."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery

from app.config import get_settings
from app.database import async_session_factory
from app.models import PaymentProduct, PaymentStatus
from app.services.payments import (
    complete_ad_payment,
    complete_credit_payment,
    complete_publish_payment,
    get_payment_by_payload,
    parse_any_payment_payload,
)

logger = logging.getLogger(__name__)
router = Router(name="payments")


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    payload = query.invoice_payload or ""
    kind = parse_any_payment_payload(payload)
    if kind is None:
        await query.answer(ok=False, error_message="Unknown invoice")
        return

    async with async_session_factory() as session:
        payment = await get_payment_by_payload(session, payload)
        if payment is None:
            await query.answer(ok=False, error_message="Payment not found")
            return
        allowed = {
            PaymentProduct.PROFILE_PUBLISH.value,
            PaymentProduct.MESSAGE_CREDIT.value,
            PaymentProduct.MESSAGE_PACK_9.value,
            PaymentProduct.AD_SLOT.value,
        }
        if payment.product not in allowed:
            await query.answer(ok=False, error_message="Unsupported product")
            return
        if payment.stars_amount != query.total_amount:
            await query.answer(ok=False, error_message="Amount mismatch")
            return
        if payment.status != PaymentStatus.PENDING.value:
            await query.answer(ok=False, error_message="Счёт устарел. Используйте последний счёт в чате.")
            return

    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message) -> None:
    payment_info = message.successful_payment
    if payment_info is None:
        return
    payload = payment_info.invoice_payload
    settings = get_settings()

    async with async_session_factory() as session:
        payment = await get_payment_by_payload(session, payload)
        if payment is None:
            logger.error("successful_payment with unknown payload: %s", payload)
            return
        if payment.product == PaymentProduct.PROFILE_PUBLISH.value:
            await complete_publish_payment(
                session,
                settings,
                payment=payment,
                telegram_charge_id=payment_info.telegram_payment_charge_id,
            )
        elif payment.product in {
            PaymentProduct.MESSAGE_CREDIT.value,
            PaymentProduct.MESSAGE_PACK_9.value,
        }:
            await complete_credit_payment(
                session,
                settings,
                payment=payment,
                telegram_charge_id=payment_info.telegram_payment_charge_id,
            )
        elif payment.product == PaymentProduct.AD_SLOT.value:
            await complete_ad_payment(
                session,
                settings,
                payment=payment,
                telegram_charge_id=payment_info.telegram_payment_charge_id,
            )
        else:
            logger.warning("Unhandled payment product: %s", payment.product)
