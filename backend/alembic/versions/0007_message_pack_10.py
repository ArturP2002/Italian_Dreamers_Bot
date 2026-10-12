"""message pack product renamed: 9 -> 10 messages

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE payments SET product = 'message_pack_10' WHERE product = 'message_pack_9'")
    op.execute("UPDATE credit_ledger SET note = 'pack_10' WHERE note = 'pack_9'")


def downgrade() -> None:
    op.execute("UPDATE payments SET product = 'message_pack_9' WHERE product = 'message_pack_10'")
    op.execute("UPDATE credit_ledger SET note = 'pack_9' WHERE note = 'pack_10'")
