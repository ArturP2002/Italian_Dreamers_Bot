"""Letter pay-at-send, 3-day reply timeout and refund fields.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "message_requests",
        sa.Column("paid_at_send", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "message_requests",
        sa.Column("credit_held", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "message_requests",
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("message_requests", "refunded_at")
    op.drop_column("message_requests", "credit_held")
    op.drop_column("message_requests", "paid_at_send")
