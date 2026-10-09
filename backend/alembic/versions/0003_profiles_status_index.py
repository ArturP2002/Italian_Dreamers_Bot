"""index profiles by status + updated_at for admin lists

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_profiles_status_updated_at",
        "profiles",
        ["status", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_profiles_status_updated_at", table_name="profiles")
