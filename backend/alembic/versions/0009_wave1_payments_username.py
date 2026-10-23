"""Wave 1: payment provider fields, username nudges, unpaid reminders

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_platform", sa.String(32), nullable=True))
    op.add_column(
        "users",
        sa.Column("bot_write_access", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("users", sa.Column("bot_write_access_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("username_nudge_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("username_nudge_2_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("profiles", sa.Column("unpaid_reminded_3d_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("profiles", sa.Column("unpaid_reminded_14d_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("profiles", sa.Column("unpaid_reminded_27d_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        "payments",
        sa.Column("provider", sa.String(32), nullable=False, server_default="stars"),
    )
    op.add_column(
        "payments",
        sa.Column("currency", sa.String(8), nullable=False, server_default="XTR"),
    )
    op.add_column(
        "payments",
        sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("payments", sa.Column("provider_payment_id", sa.String(255), nullable=True))
    op.create_index("ix_payments_provider_payment_id", "payments", ["provider_payment_id"])
    op.execute("UPDATE payments SET amount = stars_amount WHERE amount = 0")


def downgrade() -> None:
    op.drop_index("ix_payments_provider_payment_id", table_name="payments")
    op.drop_column("payments", "provider_payment_id")
    op.drop_column("payments", "amount")
    op.drop_column("payments", "currency")
    op.drop_column("payments", "provider")
    op.drop_column("profiles", "unpaid_reminded_27d_at")
    op.drop_column("profiles", "unpaid_reminded_14d_at")
    op.drop_column("profiles", "unpaid_reminded_3d_at")
    op.drop_column("users", "username_nudge_2_at")
    op.drop_column("users", "username_nudge_sent_at")
    op.drop_column("users", "bot_write_access_at")
    op.drop_column("users", "bot_write_access")
    op.drop_column("users", "telegram_platform")
