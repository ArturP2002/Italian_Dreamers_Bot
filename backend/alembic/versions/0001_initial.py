"""initial schema: users, profiles, messaging, payments, ads, complaints

Revision ID: 0001
Revises:
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("telegram_first_name", sa.String(length=255), nullable=True),
        sa.Column("telegram_last_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=2), nullable=False, server_default="ru"),
        sa.Column("gender", sa.String(length=16), nullable=True),
        sa.Column("stated_age", sa.Integer(), nullable=True),
        sa.Column("stated_name", sa.String(length=20), nullable=True),
        sa.Column("stated_photo_file_id", sa.String(length=1024), nullable=True),
        sa.Column("stated_photo_file_unique_id", sa.String(length=255), nullable=True),
        sa.Column("message_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("soft_ban_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("referral_code", sa.String(length=32), nullable=True),
        sa.Column("referred_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)
    op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)

    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("age", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("age_min", sa.Integer(), nullable=False, server_default="18"),
        sa.Column("age_max", sa.Integer(), nullable=False, server_default="99"),
        sa.Column("height_cm", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_children", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("gender", sa.String(length=16), nullable=True),
        sa.Column("wants_children", sa.String(length=16), nullable=False, server_default="unsure"),
        sa.Column("marital_status", sa.String(length=32), nullable=False, server_default="single"),
        sa.Column("country", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("city", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("profession", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("hobbies", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("about", sa.Text(), nullable=False, server_default=""),
        sa.Column("desired_partner", sa.Text(), nullable=False, server_default=""),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("personal_data_agreement", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("publication_option", sa.String(length=32), nullable=False, server_default="standard"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("cover_question_id", sa.Integer(), nullable=True),
        sa.Column("cover_answer", sa.String(length=70), nullable=True),
        sa.Column("dream_location", sa.String(length=64), nullable=True),
        sa.Column("moderation_feedback", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel_message_id", sa.BigInteger(), nullable=True),
        sa.Column("splash_message_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name_translated", sa.String(length=255), nullable=True),
        sa.Column("city_translated", sa.String(length=255), nullable=True),
        sa.Column("country_translated", sa.String(length=255), nullable=True),
        sa.Column("profession_translated", sa.Text(), nullable=True),
        sa.Column("about_translated", sa.Text(), nullable=True),
        sa.Column("desired_partner_translated", sa.Text(), nullable=True),
        sa.Column("cover_answer_translated", sa.String(length=70), nullable=True),
        sa.Column("translated_language", sa.String(length=2), nullable=True),
        sa.Column("translated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_profiles_scheduled_at", "profiles", ["scheduled_at"])

    op.create_table(
        "profile_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(length=1024), nullable=False),
        sa.Column("file_unique_id", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("profile_id", "position", name="uq_profile_photos_profile_position"),
    )

    op.create_table(
        "message_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_translated", sa.Text(), nullable=True),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column("reply_text_translated", sa.Text(), nullable=True),
        sa.Column("sender_name", sa.String(length=64), nullable=True),
        sa.Column("sender_age", sa.Integer(), nullable=True),
        sa.Column("sender_photo_file_id", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("charged_payment_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_message_requests_profile_id", "message_requests", ["profile_id"])
    op.create_index("ix_message_requests_sender_user_id", "message_requests", ["sender_user_id"])
    op.create_index("ix_message_requests_status", "message_requests", ["status"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "message_request_id",
            sa.Integer(),
            sa.ForeignKey("message_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_translated", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_messages_message_request_id", "chat_messages", ["message_request_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("stars_amount", sa.Integer(), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(length=255), nullable=True),
        sa.Column("telegram_payload", sa.String(length=255), nullable=True),
        sa.Column("related_profile_id", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("related_message_request_id", sa.Integer(), nullable=True),
        sa.Column("related_ad_request_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("telegram_payment_charge_id", name="uq_payments_charge_id"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_telegram_payload", "payments", ["telegram_payload"])
    op.create_index("ix_payments_related_message_request_id", "payments", ["related_message_request_id"])
    op.create_index("ix_payments_related_ad_request_id", "payments", ["related_ad_request_id"])

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "message_request_id",
            sa.Integer(),
            sa.ForeignKey("message_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_credit_ledger_user_id", "credit_ledger", ["user_id"])

    op.create_table(
        "ad_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("contact", sa.String(length=255), nullable=True),
        sa.Column("media_file_id", sa.String(length=1024), nullable=True),
        sa.Column("moderation_feedback", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel_message_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ad_requests_user_id", "ad_requests", ["user_id"])
    op.create_index("ix_ad_requests_status", "ad_requests", ["status"])
    op.create_index("ix_ad_requests_scheduled_at", "ad_requests", ["scheduled_at"])

    op.create_table(
        "complaints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reporter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reported_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "message_request_id",
            sa.Integer(),
            sa.ForeignKey("message_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_complaints_reporter_user_id", "complaints", ["reporter_user_id"])
    op.create_index("ix_complaints_reported_user_id", "complaints", ["reported_user_id"])
    op.create_index("ix_complaints_status", "complaints", ["status"])


def downgrade() -> None:
    op.drop_table("complaints")
    op.drop_table("ad_requests")
    op.drop_table("credit_ledger")
    op.drop_table("payments")
    op.drop_table("chat_messages")
    op.drop_table("message_requests")
    op.drop_table("profile_photos")
    op.drop_table("profiles")
    op.drop_table("users")
