"""replace dream_location with optional greeting video

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("greeting_video_file_id", sa.String(length=255), nullable=True),
    )
    op.drop_column("profiles", "dream_location")


def downgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("dream_location", sa.String(length=64), nullable=True),
    )
    op.drop_column("profiles", "greeting_video_file_id")
