"""Wave 2: daily publication slots for the channel queue.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "publication_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slot_date", sa.Date(), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("time_local", sa.String(5), nullable=False),
        sa.Column("gender", sa.String(16), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("slot_date", "slot_index", name="uq_publication_slots_date_index"),
    )
    op.create_index("ix_publication_slots_slot_date", "publication_slots", ["slot_date"])
    op.create_index("ix_publication_slots_profile_id", "publication_slots", ["profile_id"])


def downgrade() -> None:
    op.drop_index("ix_publication_slots_profile_id", table_name="publication_slots")
    op.drop_index("ix_publication_slots_slot_date", table_name="publication_slots")
    op.drop_table("publication_slots")
