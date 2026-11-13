"""Plus-only shift: referral reward flag, cut notify, renewal remind, newcomers.

Revision ID: 0017_plus_only_shift
Revises: 0016
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_plus_only_shift"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "referral_plus_rewarded",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "users",
        sa.Column("credits_cut_notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("renewal_reminded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("newcomers_collage_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("newcomers_batch_date", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "newcomers_batch_date")
    op.drop_column("profiles", "newcomers_collage_at")
    op.drop_column("subscriptions", "renewal_reminded_at")
    op.drop_column("users", "credits_cut_notified_at")
    op.drop_column("users", "referral_plus_rewarded")
