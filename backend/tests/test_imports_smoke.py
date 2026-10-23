"""Import every API/bot surface so missing Wave 3 wiring fails in CI, not in Telegram."""

from __future__ import annotations


def test_api_package_imports() -> None:
    from app.api import api_router
    from app.api import admin_wave3, catalog, likes, me, messages, profile

    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/me" in paths or any("/me" in (getattr(r, "path", "") or "") for r in api_router.routes)
    assert admin_wave3.router is not None
    assert likes.router is not None
    assert catalog.router is not None
    assert me.router is not None
    assert messages.router is not None
    assert profile.router is not None


def test_wave3_services_import() -> None:
    from app.models import PaymentProduct, VerificationStatus
    from app.services import comments_ai, entitlements, legacy, likes, verification, weekly_report

    assert PaymentProduct.UNLIMITED_SUB.value == "unlimited_sub"
    assert PaymentProduct.CATALOG_TOP.value == "catalog_top"
    assert VerificationStatus.PENDING.value == "pending"
    assert comments_ai.parse_classifier_reply
    assert entitlements.has_unlimited
    assert legacy.claim_legacy
    assert likes.toggle_like
    assert verification.submit_selfie
    assert weekly_report.report_window


def test_bot_handlers_import() -> None:
    import sys
    from pathlib import Path

    bot_root = Path(__file__).resolve().parents[2] / "bot"
    if str(bot_root) not in sys.path:
        sys.path.insert(0, str(bot_root))
    from handlers import comments, discussion, payments, start, username  # noqa: F401

    assert comments.router is not None
    assert payments.router is not None
