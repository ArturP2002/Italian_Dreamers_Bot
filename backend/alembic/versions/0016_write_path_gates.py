"""Write-path gifts, registration gates, teaser photos, catalog views.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("gift_credits_granted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("gift_credits_left", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("first_message_free_used", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("registration_bonus_granted", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.add_column(
        "message_requests",
        sa.Column("hidden_by_sender", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "message_requests",
        sa.Column("hidden_by_recipient", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "message_requests",
        sa.Column("sender_telegram_shared_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "message_requests",
        sa.Column("recipient_telegram_shared_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "message_requests",
        sa.Column("unlock_from_gift", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "catalog_profile_views",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("view_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "profile_id", "view_date", name="uq_catalog_views_user_profile_day"),
    )
    op.create_index("ix_catalog_profile_views_user_date", "catalog_profile_views", ["user_id", "view_date"])

    op.create_table(
        "waiting_teaser_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("audience_gender", sa.String(16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.String(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("audience_gender", "position", name="uq_waiting_teaser_gender_pos"),
    )


def downgrade() -> None:
    op.drop_table("waiting_teaser_photos")
    op.drop_index("ix_catalog_profile_views_user_date", table_name="catalog_profile_views")
    op.drop_table("catalog_profile_views")
    op.drop_column("message_requests", "unlock_from_gift")
    op.drop_column("message_requests", "recipient_telegram_shared_at")
    op.drop_column("message_requests", "sender_telegram_shared_at")
    op.drop_column("message_requests", "hidden_by_recipient")
    op.drop_column("message_requests", "hidden_by_sender")
    op.drop_column("users", "registration_bonus_granted")
    op.drop_column("users", "first_message_free_used")
    op.drop_column("users", "gift_credits_left")
    op.drop_column("users", "gift_credits_granted")
