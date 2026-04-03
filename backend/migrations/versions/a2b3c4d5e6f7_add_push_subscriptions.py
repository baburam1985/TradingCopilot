"""add push_subscriptions table

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-04-03 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trading_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(2048), nullable=False),
        sa.Column("p256dh", sa.String(512), nullable=False),
        sa.Column("auth", sa.String(256), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_push_subscriptions_session_id",
        "push_subscriptions",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_session_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
