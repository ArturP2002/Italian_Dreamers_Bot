"""ads: category, desired_date, reminder timestamps

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ad_requests",
        sa.Column("category", sa.String(length=64), nullable=False, server_default="other"),
    )
    op.add_column(
        "ad_requests",
        sa.Column("desired_date", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ad_requests",
        sa.Column("reminded_7d_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "ad_requests",
        sa.Column("reminded_30d_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ad_requests", "reminded_30d_at")
    op.drop_column("ad_requests", "reminded_7d_at")
    op.drop_column("ad_requests", "desired_date")
    op.drop_column("ad_requests", "category")
