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
    PaymentCurrency,
    PaymentProduct,
    PaymentProvider,
    PaymentStatus,
    Profile,
    ProfileStatus,
    Subscription,
    SubscriptionStatus,
    User,
)
from app.services.entitlements import (
    SUBSCRIPTION_PERIOD,
    active_subscription,
    apply_top_for_user,
    apply_top_until,
    utcnow,
)
from app.services.telegram_api import edit_user_star_subscription, send_invoice_stars, send_message


PAYLOAD_PREFIX = "pub"
CREDIT_PAYLOAD_PREFIX = "cred"
PACK_PAYLOAD_PREFIX = "pack"
AD_PAYLOAD_PREFIX = "ad"
SUB_PAYLOAD_PREFIX = "sub"
TOP_PAYLOAD_PREFIX = "top"


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


def _stars_fields(stars: int) -> dict:
    return {
        "provider": PaymentProvider.STARS.value,
        "currency": PaymentCurrency.XTR.value,
        "amount": stars,
        "stars_amount": stars,
    }


def _mark_provider_paid(payment: Payment, *, provider_payment_id: str | None) -> None:
    if provider_payment_id:
        payment.provider_payment_id = provider_payment_id
        payment.telegram_payment_charge_id = provider_payment_id
    if not payment.provider:
        payment.provider = PaymentProvider.STARS.value
    if not payment.currency:
        payment.currency = PaymentCurrency.XTR.value
    if not payment.amount:
        payment.amount = payment.stars_amount


def make_sub_payload(payment_id: int) -> str:
    return f"{SUB_PAYLOAD_PREFIX}:{payment_id}"


def parse_sub_payload(payload: str) -> int | None:
    parts = payload.split(":")
    if len(parts) != 2 or parts[0] != SUB_PAYLOAD_PREFIX:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def make_top_payload(payment_id: int, profile_id: int) -> str:
    return f"{TOP_PAYLOAD_PREFIX}:{payment_id}:{profile_id}"


def parse_top_payload(payload: str) -> tuple[int, int] | None:
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != TOP_PAYLOAD_PREFIX:
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


def parse_any_payment_payload(payload: str) -> str | None:
    """Return product kind: publish | credit | pack | ad | sub | top."""
    if parse_publish_payload(payload):
        return "publish"
    if parse_credit_payload(payload):
        return "credit"
    if parse_pack_payload(payload):
        return "pack"
    if parse_ad_payload(payload):
        return "ad"
    if parse_sub_payload(payload) is not None:
        return "sub"
    if parse_top_payload(payload):
        return "top"
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
        related_profile_id=profile.id,
        **_stars_fields(settings.price_profile_publish_stars),
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
    _mark_provider_paid(payment, provider_payment_id=telegram_charge_id)
    session.add(payment)

    result = await session.execute(select(Profile).where(Profile.id == payment.related_profile_id))
    profile = result.scalar_one()
    profile.status = ProfileStatus.QUEUED.value
    profile.paid_at = datetime.now(timezone.utc)
    session.add(profile)
    await session.flush()

    from app.services.notify import notify_user_scheduled
    from app.services.slots import assign_next_slot

    slot = await assign_next_slot(session, settings, profile)
    await session.commit()
    await session.refresh(profile)

    user_result = await session.execute(select(User).where(User.id == payment.user_id))
    user = user_result.scalar_one()
    if slot is not None and profile.scheduled_at is not None:
        await notify_user_scheduled(
            settings, user=user, profile=profile, scheduled_at=profile.scheduled_at
        )
    else:
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
        product = PaymentProduct.MESSAGE_PACK_10.value
        stars = settings.price_message_pack_10_stars
        make_payload = make_pack_payload
    else:
        product = PaymentProduct.MESSAGE_CREDIT.value
        stars = settings.price_message_credit_stars
        make_payload = make_credit_payload

    payment = Payment(
        user_id=user.id,
        product=product,
        status=PaymentStatus.PENDING.value,
        related_message_request_id=message_request_id,
        **_stars_fields(stars),
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
    is_pack = payment.product == PaymentProduct.MESSAGE_PACK_10.value
    if lang == "it":
        if is_pack:
            title = f"Pacchetto {settings.message_pack_size} messaggi"
            description = (
                f"Pacchetto da {settings.message_pack_size} crediti messaggio. "
                "I crediti non scadono."
            )
        else:
            title = "1 credito messaggio"
            description = "Sblocca la chat con chi ti ha risposto (1 credito)."
    else:
        if is_pack:
            title = f"Пакет {settings.message_pack_size} сообщений"
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

    is_pack = payment.product == PaymentProduct.MESSAGE_PACK_10.value
    delta = settings.message_pack_size if is_pack else 1

    payment.status = PaymentStatus.COMPLETED.value
    payment.completed_at = datetime.now(timezone.utc)
    _mark_provider_paid(payment, provider_payment_id=telegram_charge_id)
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
            note="pack_10" if is_pack else "credit_1",
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
        related_ad_request_id=ad.id,
        **_stars_fields(settings.price_ad_slot_stars),
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
    _mark_provider_paid(payment, provider_payment_id=telegram_charge_id)
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


async def queue_profile_after_entitlement(
    session: AsyncSession,
    settings: Settings,
    *,
    profile: Profile,
    user: User,
) -> Profile:
    """Move awaiting_payment profile to queued + slot without a publish invoice."""
    if profile.status != ProfileStatus.AWAITING_PAYMENT.value:
        return profile
    profile.status = ProfileStatus.QUEUED.value
    profile.paid_at = profile.paid_at or utcnow()
    session.add(profile)
    await session.flush()

    from app.services.notify import notify_user_scheduled
    from app.services.slots import assign_next_slot

    slot = await assign_next_slot(session, settings, profile)
    await session.commit()
    await session.refresh(profile)
    if slot is not None and profile.scheduled_at is not None:
        await notify_user_scheduled(
            settings, user=user, profile=profile, scheduled_at=profile.scheduled_at
        )
    return profile


async def create_unlimited_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
) -> Payment:
    payment = Payment(
        user_id=user.id,
        product=PaymentProduct.UNLIMITED_SUB.value,
        status=PaymentStatus.PENDING.value,
        **_stars_fields(settings.price_unlimited_sub_stars),
    )
    session.add(payment)
    await session.flush()
    payment.telegram_payload = make_sub_payload(payment.id)
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def send_unlimited_invoice(settings: Settings, *, user: User, payment: Payment) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        title = "Abbonamento illimitato"
        description = (
            "30 giorni: lettere, pubblicazione e cima del catalogo. "
            "La pubblicità resta a parte. Rinnovo automatico Stars."
        )
    else:
        title = "Безлимит 30 дней"
        description = (
            "Письма, публикация и топ каталога на 30 дней. "
            "Реклама отдельно. Автопродление Telegram Stars."
        )
    await send_invoice_stars(
        settings,
        user.telegram_id,
        title=title,
        description=description,
        payload=payment.telegram_payload or make_sub_payload(payment.id),
        stars_amount=payment.stars_amount,
        label=title,
        subscription_period=settings.subscription_period_seconds,
    )


def _expiry_from_telegram(timestamp: int | None) -> datetime:
    if timestamp:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    return utcnow() + SUBSCRIPTION_PERIOD


async def _upsert_subscription(
    session: AsyncSession,
    *,
    user: User,
    payment: Payment,
    expires_at: datetime,
    charge_id: str | None,
) -> Subscription:
    existing = await active_subscription(session, user.id)
    now = utcnow()
    if existing is None:
        existing = Subscription(
            user_id=user.id,
            status=SubscriptionStatus.ACTIVE.value,
            started_at=now,
            expires_at=expires_at,
            telegram_charge_id=charge_id,
            payment_id=payment.id,
        )
    else:
        if existing.expires_at < expires_at:
            existing.expires_at = expires_at
        existing.status = SubscriptionStatus.ACTIVE.value
        existing.canceled_at = None
        if charge_id:
            existing.telegram_charge_id = charge_id
        existing.payment_id = payment.id
    session.add(existing)
    await apply_top_for_user(session, user.id, existing.expires_at)
    return existing


async def complete_unlimited_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    payment: Payment,
    telegram_charge_id: str | None,
    subscription_expiration_date: int | None = None,
) -> Subscription:
    user_result = await session.execute(select(User).where(User.id == payment.user_id))
    user = user_result.scalar_one()
    expires_at = _expiry_from_telegram(subscription_expiration_date)

    if payment.status == PaymentStatus.COMPLETED.value:
        if telegram_charge_id and telegram_charge_id != payment.telegram_payment_charge_id:
            renewal = Payment(
                user_id=user.id,
                product=PaymentProduct.UNLIMITED_SUB.value,
                status=PaymentStatus.COMPLETED.value,
                completed_at=utcnow(),
                telegram_payload=payment.telegram_payload,
                **_stars_fields(payment.stars_amount or settings.price_unlimited_sub_stars),
            )
            _mark_provider_paid(renewal, provider_payment_id=telegram_charge_id)
            session.add(renewal)
            await session.flush()
            sub = await _upsert_subscription(
                session, user=user, payment=renewal, expires_at=expires_at, charge_id=telegram_charge_id
            )
            await session.commit()
            await session.refresh(sub)
            return sub
        sub = await active_subscription(session, user.id)
        if sub is not None:
            return sub
        sub = await _upsert_subscription(
            session, user=user, payment=payment, expires_at=expires_at, charge_id=telegram_charge_id
        )
        await session.commit()
        return sub

    payment.status = PaymentStatus.COMPLETED.value
    payment.completed_at = utcnow()
    _mark_provider_paid(payment, provider_payment_id=telegram_charge_id)
    session.add(payment)
    sub = await _upsert_subscription(
        session, user=user, payment=payment, expires_at=expires_at, charge_id=telegram_charge_id
    )
    await session.commit()

    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    until = sub.expires_at.astimezone(timezone.utc).strftime("%d.%m.%Y")
    if lang == "it":
        text = (
            "✅ Abbonamento illimitato attivo fino al "
            f"<b>{until}</b>.\nLettere, pubblicazione e cima del catalogo sono inclusi."
        )
    else:
        text = (
            "✅ Безлимит активен до "
            f"<b>{until}</b>.\nПисьма, публикация и топ каталога включены."
        )
    await send_message(settings, user.telegram_id, text)

    profile_result = await session.execute(select(Profile).where(Profile.user_id == user.id))
    profile = profile_result.scalar_one_or_none()
    if profile is not None and profile.status == ProfileStatus.AWAITING_PAYMENT.value:
        await queue_profile_after_entitlement(session, settings, profile=profile, user=user)
    return sub


async def cancel_unlimited_subscription(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
) -> Subscription | None:
    sub = await active_subscription(session, user.id)
    if sub is None:
        return None
    sub.status = SubscriptionStatus.CANCELED.value
    sub.canceled_at = utcnow()
    session.add(sub)
    await session.commit()
    if sub.telegram_charge_id:
        try:
            await edit_user_star_subscription(
                settings,
                user.telegram_id,
                sub.telegram_charge_id,
                is_canceled=True,
            )
        except Exception:
            pass
    return sub


async def create_catalog_top_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    user: User,
    profile: Profile,
) -> Payment:
    payment = Payment(
        user_id=user.id,
        product=PaymentProduct.CATALOG_TOP.value,
        status=PaymentStatus.PENDING.value,
        related_profile_id=profile.id,
        **_stars_fields(settings.price_catalog_top_stars),
    )
    session.add(payment)
    await session.flush()
    payment.telegram_payload = make_top_payload(payment.id, profile.id)
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def send_catalog_top_invoice(
    settings: Settings,
    *,
    user: User,
    profile: Profile,
    payment: Payment,
) -> None:
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    if lang == "it":
        title = "Cima del catalogo"
        description = f"30 giorni in cima al catalogo Mini App per {profile.name}."
    else:
        title = "Топ каталога"
        description = f"30 дней в топе каталога Mini App для {profile.name}."
    await send_invoice_stars(
        settings,
        user.telegram_id,
        title=title,
        description=description,
        payload=payment.telegram_payload or make_top_payload(payment.id, profile.id),
        stars_amount=payment.stars_amount,
        label=title,
    )


async def complete_catalog_top_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    payment: Payment,
    telegram_charge_id: str | None,
) -> Profile:
    result = await session.execute(select(Profile).where(Profile.id == payment.related_profile_id))
    profile = result.scalar_one()
    if payment.status == PaymentStatus.COMPLETED.value:
        return profile
    payment.status = PaymentStatus.COMPLETED.value
    payment.completed_at = utcnow()
    _mark_provider_paid(payment, provider_payment_id=telegram_charge_id)
    session.add(payment)
    until = utcnow() + SUBSCRIPTION_PERIOD
    if profile.top_until and profile.top_until > utcnow():
        until = profile.top_until + SUBSCRIPTION_PERIOD
    apply_top_until(profile, until)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    user_result = await session.execute(select(User).where(User.id == payment.user_id))
    user = user_result.scalar_one()
    lang = user.language_code if user.language_code in {"ru", "it"} else "ru"
    stamp = profile.top_until.strftime("%d.%m.%Y") if profile.top_until else "—"
    if lang == "it":
        text = f"✅ Sei in cima al catalogo fino al <b>{stamp}</b>."
    else:
        text = f"✅ Анкета в топе каталога до <b>{stamp}</b>."
    await send_message(settings, user.telegram_id, text)
    return profile


async def complete_payment(
    session: AsyncSession,
    settings: Settings,
    *,
    payment: Payment,
    provider_payment_id: str | None,
    subscription_expiration_date: int | None = None,
):
    """Idempotent fulfillment. Stars and (later) YooKassa both call this."""
    if payment.product == PaymentProduct.PROFILE_PUBLISH.value:
        return await complete_publish_payment(
            session, settings, payment=payment, telegram_charge_id=provider_payment_id
        )
    if payment.product in {
        PaymentProduct.MESSAGE_CREDIT.value,
        PaymentProduct.MESSAGE_PACK_10.value,
    }:
        return await complete_credit_payment(
            session, settings, payment=payment, telegram_charge_id=provider_payment_id
        )
    if payment.product == PaymentProduct.AD_SLOT.value:
        return await complete_ad_payment(
            session, settings, payment=payment, telegram_charge_id=provider_payment_id
        )
    if payment.product == PaymentProduct.UNLIMITED_SUB.value:
        return await complete_unlimited_payment(
            session,
            settings,
            payment=payment,
            telegram_charge_id=provider_payment_id,
            subscription_expiration_date=subscription_expiration_date,
        )
    if payment.product == PaymentProduct.CATALOG_TOP.value:
        return await complete_catalog_top_payment(
            session, settings, payment=payment, telegram_charge_id=provider_payment_id
        )
    raise ValueError(f"Unsupported product {payment.product}")
