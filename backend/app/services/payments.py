"""Telegram Stars payments: profile publish + message credits / packs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import (
    AdRequest,
    AdRequestStatus,
    CreditLedgerEntry,
    LedgerEntryType,
    MessageRequest,
    MessageRequestStatus,
    Payment,
    PaymentProduct,
    PaymentStatus,
    Profile,
    ProfileStatus,
    User,
)
from app.services.telegram_api import send_invoice_stars, send_message


PAYLOAD_PREFIX = "pub"
CREDIT_PAYLOAD_PREFIX = "cred"
PACK_PAYLOAD_PREFIX = "pack"
AD_PAYLOAD_PREFIX = "ad"


def make_publish_payload(payment_id: int, profile_id: int) -> str:
    return f"{PAYLOAD_PREFIX}:{payment_id}:{profile_id}"


def parse_publish_payload(payload: str) -> tuple[int, int] | None:
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != PAYLOAD_PREFIX:
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


def make_credit_payload(payment_id: int, message_request_id: int | None) -> str:
    mr = message_request_id if message_request_id is not None else 0
    return f"{CREDIT_PAYLOAD_PREFIX}:{payment_id}:{mr}"


def parse_credit_payload(payload: str) -> tuple[int, int | None] | None:
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != CREDIT_PAYLOAD_PREFIX:
        return None
    try:
        payment_id = int(parts[1])
        mr_id = int(parts[2])
        return payment_id, (mr_id if mr_id > 0 else None)
    except ValueError:
        return None


def make_pack_payload(payment_id: int, message_request_id: int | None) -> str:
    mr = message_request_id if message_request_id is not None else 0
    return f"{PACK_PAYLOAD_PREFIX}:{payment_id}:{mr}"


def parse_pack_payload(payload: str) -> tuple[int, int | None] | None:
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != PACK_PAYLOAD_PREFIX:
        return None
    try:
        payment_id = int(parts[1])
        mr_id = int(parts[2])
        return payment_id, (mr_id if mr_id > 0 else None)
    except ValueError:
        return None


def make_ad_payload(payment_id: int, ad_request_id: int) -> str:
    return f"{AD_PAYLOAD_PREFIX}:{payment_id}:{ad_request_id}"


def parse_ad_payload(payload: str) -> tuple[int, int] | None:
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != AD_PAYLOAD_PREFIX:
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


def parse_any_payment_payload(payload: str) -> str | None:
    """Return product kind: publish | credit | pack | ad."""
    if parse_publish_payload(payload):
        return "publish"
    if parse_credit_payload(payload):
        return "credit"
    if parse_pack_payload(payload):
        return "pack"
    if parse_ad_payload(payload):
        return "ad"
    return None


async def create_publish_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    profile: Profile,
) -> Payment:
    payment = Payment(
        user_id=user.id,
        product=PaymentProduct.PROFILE_PUBLISH.value,
        status=PaymentStatus.PENDING.value,
        stars_amount=settings.price_profile_publish_stars,
        related_profile_id=profile.id,
    )
    session.add(payment)
    await session.flush()
    payment.telegram_payload = make_publish_payload(payment.id, profile.id)
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def send_publish_invoice(
    settings: Settings,
    *,
    user: User,
    profile: Profile,
    payment: Payment,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        title = "Pubblicazione profilo"
        description = (
            f"Pubblicazione del profilo di {profile.name} nel canale Italian Dreamers. "
            "Dopo il pagamento entrerai in coda di pubblicazione."
        )
    else:
        title = "Публикация анкеты"
        description = (
            f"Публикация анкеты {profile.name} в канале Italian Dreamers. "
            "После оплаты анкета попадёт в очередь публикации."
        )
    await send_invoice_stars(
        settings,
        user.telegram_id,
        title=title,
        description=description,
        payload=payment.telegram_payload or make_publish_payload(payment.id, profile.id),
        stars_amount=payment.stars_amount,
        label=title,
    )


async def complete_publish_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    payment: Payment,
    telegram_charge_id: str | None,
) -> Profile:
    if payment.status == PaymentStatus.COMPLETED.value:
        result = await session.execute(select(Profile).where(Profile.id == payment.related_profile_id))
        profile = result.scalar_one()
        return profile

    payment.status = PaymentStatus.COMPLETED.value
    payment.completed_at = datetime.now(timezone.utc)
    if telegram_charge_id:
        payment.telegram_payment_charge_id = telegram_charge_id
    session.add(payment)

    result = await session.execute(select(Profile).where(Profile.id == payment.related_profile_id))
    profile = result.scalar_one()
    profile.status = ProfileStatus.QUEUED.value
    profile.paid_at = datetime.now(timezone.utc)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    user_result = await session.execute(select(User).where(User.id == payment.user_id))
    user = user_result.scalar_one()
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = (
            "✅ Pagamento ricevuto.\n\n"
            "Il tuo profilo è in coda di pubblicazione. "
            "Ti scriveremo la data esatta non appena l’amministratore la fisserà."
        )
    else:
        text = (
            "✅ Оплата получена.\n\n"
            "Анкета в очереди на публикацию. "
            "Точную дату сообщим, как только администратор назначит её в календаре."
        )
    await send_message(settings, user.telegram_id, text)
    return profile


async def get_payment_by_payload(session: AsyncSession, payload: str) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.telegram_payload == payload))
    return result.scalar_one_or_none()


async def create_credit_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    message_request_id: int | None = None,
    pack: bool = False,
) -> Payment:
    if pack:
        product = PaymentProduct.MESSAGE_PACK_9.value
        stars = settings.price_message_pack_9_stars
        make_payload = make_pack_payload
    else:
        product = PaymentProduct.MESSAGE_CREDIT.value
        stars = settings.price_message_credit_stars
        make_payload = make_credit_payload

    payment = Payment(
        user_id=user.id,
        product=product,
        status=PaymentStatus.PENDING.value,
        stars_amount=stars,
        related_message_request_id=message_request_id,
    )
    session.add(payment)
    await session.flush()
    payment.telegram_payload = make_payload(payment.id, message_request_id)
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def send_credit_invoice(
    settings: Settings,
    *,
    user: User,
    payment: Payment,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    is_pack = payment.product == PaymentProduct.MESSAGE_PACK_9.value
    if lang == "it":
        if is_pack:
            title = "Pacchetto 9 messaggi"
            description = (
                f"Pacchetto da {settings.message_pack_size} crediti messaggio. "
                "I crediti non scadono."
            )
        else:
            title = "1 credito messaggio"
            description = "Sblocca la chat con chi ti ha risposto (1 credito)."
    else:
        if is_pack:
            title = "Пакет 9 сообщений"
            description = (
                f"Пакет из {settings.message_pack_size} кредитов сообщений. "
                "Кредиты не сгорают."
            )
        else:
            title = "1 кредит сообщения"
            description = "Открыть чат с тем, кто вам ответил (1 кредит)."

    payload = payment.telegram_payload or (
        make_pack_payload(payment.id, payment.related_message_request_id)
        if is_pack
        else make_credit_payload(payment.id, payment.related_message_request_id)
    )
    await send_invoice_stars(
        settings,
        user.telegram_id,
        title=title,
        description=description,
        payload=payload,
        stars_amount=payment.stars_amount,
        label=title,
    )


async def _auto_unlock_after_purchase(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    payment: Payment,
) -> None:
    mr_id = payment.related_message_request_id
    if not mr_id:
        return
    result = await session.execute(
        select(MessageRequest)
        .where(MessageRequest.id == mr_id)
        .options(
            selectinload(MessageRequest.profile).selectinload(Profile.user),
            selectinload(MessageRequest.sender),
        )
    )
    mr = result.scalar_one_or_none()
    if mr is None or mr.sender_user_id != user.id:
        return
    if mr.status != MessageRequestStatus.REPLIED.value:
        return
    if user.message_credits < 1:
        return

    from app.services.messages import unlock_with_credit

    await unlock_with_credit(
        session,
        settings,
        mr=mr,
        actor=user,
        payment_id=payment.id,
    )


async def complete_credit_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    payment: Payment,
    telegram_charge_id: str | None,
) -> User:
    result = await session.execute(select(User).where(User.id == payment.user_id))
    user = result.scalar_one()

    if payment.status == PaymentStatus.COMPLETED.value:
        return user

    is_pack = payment.product == PaymentProduct.MESSAGE_PACK_9.value
    delta = settings.message_pack_size if is_pack else 1

    payment.status = PaymentStatus.COMPLETED.value
    payment.completed_at = datetime.now(timezone.utc)
    if telegram_charge_id:
        payment.telegram_payment_charge_id = telegram_charge_id
    session.add(payment)

    user.message_credits += delta
    session.add(user)
    session.add(
        CreditLedgerEntry(
            user_id=user.id,
            entry_type=LedgerEntryType.PURCHASE.value,
            delta=delta,
            balance_after=user.message_credits,
            payment_id=payment.id,
            message_request_id=payment.related_message_request_id,
            note="pack_9" if is_pack else "credit_1",
        )
    )
    await session.commit()
    await session.refresh(user)

    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        text = (
            f"✅ Pagamento ricevuto. Crediti: <b>{user.message_credits}</b>.\n"
            "Apri l’app per sbloccare la chat."
        )
    else:
        text = (
            f"✅ Оплата получена. Кредитов: <b>{user.message_credits}</b>.\n"
            "Откройте Mini App, чтобы разблокировать чат."
        )
    await send_message(settings, user.telegram_id, text)

    await session.refresh(user)
    await _auto_unlock_after_purchase(session, settings, user=user, payment=payment)
    result = await session.execute(select(User).where(User.id == payment.user_id))
    return result.scalar_one()


async def create_ad_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    ad: AdRequest,
) -> Payment:
    payment = Payment(
        user_id=user.id,
        product=PaymentProduct.AD_SLOT.value,
        status=PaymentStatus.PENDING.value,
        stars_amount=settings.price_ad_slot_stars,
        related_ad_request_id=ad.id,
    )
    session.add(payment)
    await session.flush()
    payment.telegram_payload = make_ad_payload(payment.id, ad.id)
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def send_ad_invoice(
    settings: Settings,
    *,
    user: User,
    ad: AdRequest,
    payment: Payment,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        title = "Slot pubblicitario 48h"
        description = (
            f"Pubblicazione «{ad.title}» nel canale Italian Dreamers per 48 ore. "
            "Lo slot parte alle 10:00 (ora di Roma) in coda FIFO."
        )
    else:
        title = "Рекламный слот 48ч"
        description = (
            f"Публикация «{ad.title}» в канале Italian Dreamers на 48 часов. "
            "Слот стартует в 10:00 (по Риму) по очереди FIFO."
        )
    await send_invoice_stars(
        settings,
        user.telegram_id,
        title=title,
        description=description,
        payload=payment.telegram_payload or make_ad_payload(payment.id, ad.id),
        stars_amount=payment.stars_amount,
        label=title,
    )


async def complete_ad_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    payment: Payment,
    telegram_charge_id: str | None,
) -> AdRequest:
    from app.services.ads import compute_next_ad_slot

    result = await session.execute(select(AdRequest).where(AdRequest.id == payment.related_ad_request_id))
    ad = result.scalar_one()

    if payment.status == PaymentStatus.COMPLETED.value:
        return ad

    payment.status = PaymentStatus.COMPLETED.value
    payment.completed_at = datetime.now(timezone.utc)
    if telegram_charge_id:
        payment.telegram_payment_charge_id = telegram_charge_id
    session.add(payment)

    ad.status = AdRequestStatus.QUEUED.value
    ad.paid_at = datetime.now(timezone.utc)
    ad.scheduled_at = await compute_next_ad_slot(session, settings)
    session.add(ad)
    await session.commit()
    await session.refresh(ad)

    user_result = await session.execute(select(User).where(User.id == payment.user_id))
    user = user_result.scalar_one()
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    slot_local = ""
    if ad.scheduled_at:
        from zoneinfo import ZoneInfo

        local = ad.scheduled_at.astimezone(ZoneInfo(settings.app_timezone))
        slot_local = local.strftime("%d.%m.%Y %H:%M")
    if lang == "it":
        text = (
            "✅ Pagamento ricevuto.\n\n"
            "La tua pubblicità è in coda FIFO.\n"
            f"Slot previsto: <b>{slot_local or '—'}</b> (ora di Roma), durata 48 ore."
        )
    else:
        text = (
            "✅ Оплата получена.\n\n"
            "Реклама в очереди FIFO.\n"
            f"Слот: <b>{slot_local or '—'}</b> (по Риму), длительность 48 часов."
        )
    await send_message(settings, user.telegram_id, text)
    return ad
