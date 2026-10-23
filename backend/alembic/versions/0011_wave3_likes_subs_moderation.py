"""Wave 3: likes, verification, subscriptions, catalog top, comments, legacy, reports.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("verification_status", sa.String(16), nullable=False, server_default="none"),
    )
    op.add_column("profiles", sa.Column("verification_photo_file_id", sa.String(1024), nullable=True))
    op.add_column("profiles", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("profiles", sa.Column("top_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_profiles_top_until", "profiles", ["top_until"])

    op.create_table(
        "likes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("from_user_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("from_user_id", "profile_id", name="uq_likes_user_profile"),
    )
    op.create_index("ix_likes_from_user_id", "likes", ["from_user_id"])
    op.create_index("ix_likes_profile_id", "likes", ["profile_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_charge_id", sa.String(255), nullable=True),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    op.create_index("ix_subscriptions_expires_at", "subscriptions", ["expires_at"])

    op.create_table(
        "group_comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("decision", sa.String(32), nullable=False, server_default="keep"),
        sa.Column("reason", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_group_comments_chat_id", "group_comments", ["chat_id"])
    op.create_index("ix_group_comments_telegram_user_id", "group_comments", ["telegram_user_id"])
    op.create_index("ix_group_comments_decision", "group_comments", ["decision"])

    op.create_table(
        "group_strikes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restricted_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("telegram_user_id", name="uq_group_strikes_user"),
    )
    op.create_index("ix_group_strikes_telegram_user_id", "group_strikes", ["telegram_user_id"])

    op.create_table(
        "legacy_anketas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("channel_message_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("gender", sa.String(16), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("telegram_username", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("invite_token", sa.String(64), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["activated_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("invite_token", name="uq_legacy_anketas_invite_token"),
    )
    op.create_index("ix_legacy_anketas_status", "legacy_anketas", ["status"])

    op.create_table(
        "weekly_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("period_end", name="uq_weekly_reports_period_end"),
    )


def downgrade() -> None:
    op.drop_table("weekly_reports")
    op.drop_table("legacy_anketas")
    op.drop_index("ix_group_strikes_telegram_user_id", table_name="group_strikes")
    op.drop_table("group_strikes")
    op.drop_index("ix_group_comments_decision", table_name="group_comments")
    op.drop_index("ix_group_comments_telegram_user_id", table_name="group_comments")
    op.drop_index("ix_group_comments_chat_id", table_name="group_comments")
    op.drop_table("group_comments")
    op.drop_index("ix_subscriptions_expires_at", table_name="subscriptions")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_likes_profile_id", table_name="likes")
    op.drop_index("ix_likes_from_user_id", table_name="likes")
    op.drop_table("likes")
    op.drop_index("ix_profiles_top_until", table_name="profiles")
    op.drop_column("profiles", "top_until")
    op.drop_column("profiles", "verified_at")
    op.drop_column("profiles", "verification_photo_file_id")
    op.drop_column("profiles", "verification_status")
