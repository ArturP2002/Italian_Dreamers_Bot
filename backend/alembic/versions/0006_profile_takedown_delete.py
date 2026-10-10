"""take-down deletes the profile: letters survive it, takedown journal

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _profile_fk_name() -> str:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys("message_requests"):
        if fk["referred_table"] == "profiles" and fk["constrained_columns"] == ["profile_id"]:
            return fk["name"]
    raise RuntimeError("message_requests.profile_id foreign key not found")


def upgrade() -> None:
    op.drop_constraint(_profile_fk_name(), "message_requests", type_="foreignkey")
    op.alter_column("message_requests", "profile_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "message_requests_profile_id_fkey",
        "message_requests",
        "profiles",
        ["profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("message_requests", sa.Column("profile_name_snapshot", sa.String(255), nullable=True))
    op.add_column(
        "message_requests",
        sa.Column(
            "profile_owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="message_requests_profile_owner_user_id_fkey"),
            nullable=True,
        ),
    )
    op.add_column(
        "message_requests",
        sa.Column("profile_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "profile_takedowns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("age", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gender", sa.String(16), nullable=True),
        sa.Column("city", sa.String(255), nullable=False, server_default=""),
        sa.Column("country", sa.String(255), nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "admin_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("deleted_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed_letters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_chats", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_notified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_profile_takedowns_user_id", "profile_takedowns", ["user_id"])
    op.create_index("ix_profile_takedowns_created_at", "profile_takedowns", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_profile_takedowns_created_at", table_name="profile_takedowns")
    op.drop_index("ix_profile_takedowns_user_id", table_name="profile_takedowns")
    op.drop_table("profile_takedowns")
    op.drop_column("message_requests", "profile_deleted_at")
    op.drop_column("message_requests", "profile_owner_user_id")
    op.drop_column("message_requests", "profile_name_snapshot")
    op.execute("DELETE FROM message_requests WHERE profile_id IS NULL")
    op.drop_constraint("message_requests_profile_id_fkey", "message_requests", type_="foreignkey")
    op.alter_column("message_requests", "profile_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "message_requests_profile_id_fkey",
        "message_requests",
        "profiles",
        ["profile_id"],
        ["id"],
        ondelete="CASCADE",
    )
