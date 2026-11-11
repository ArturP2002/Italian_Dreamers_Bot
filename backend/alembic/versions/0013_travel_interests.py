"""Travel interest waitlist for home Travel card.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "travel_interests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_travel_interests_user_id"),
    )
    op.create_index("ix_travel_interests_user_id", "travel_interests", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_travel_interests_user_id", table_name="travel_interests")
    op.drop_table("travel_interests")
