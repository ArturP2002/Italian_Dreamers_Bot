"""Wave 1 config defaults and module imports."""

from __future__ import annotations

from app.config import Settings


def test_rate_limits_match_wave1() -> None:
    settings = Settings()  # type: ignore[call-arg]
    assert settings.rate_contact_per_hour == 50
    assert settings.rate_contact_per_day == 100
    assert settings.rate_max_pending_outgoing == 0
    assert settings.rate_soft_ban_hours == 0


def test_reserved_rub_prices_exist_unused() -> None:
    settings = Settings()  # type: ignore[call-arg]
    assert settings.price_message_credit_rub == 0
    assert settings.price_profile_publish_rub == 0
    assert settings.discussion_chat_id == 0


def test_wave1_modules_import() -> None:
    from app.api import me, messages, profile  # noqa: F401
    from app.models import PaymentCurrency, PaymentProvider
    from app.services import discussion, unpaid, username_nudge, vision  # noqa: F401
    from app.services.payments import complete_payment  # noqa: F401

    assert PaymentProvider.STARS.value == "stars"
    assert PaymentProvider.YOOKASSA.value == "yookassa"
    assert PaymentCurrency.XTR.value == "XTR"
    assert PaymentCurrency.RUB.value == "RUB"


def test_bot_wave1_handlers_import() -> None:
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    bot_root = str(repo / "bot")
    if bot_root not in sys.path:
        sys.path.insert(0, bot_root)
    from handlers import discussion, payments, username  # noqa: F401
