"""add watchlist_items table

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-04-03 03:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'watchlist_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('strategy', sa.String(length=100), nullable=False),
        sa.Column('strategy_params', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('alert_threshold', sa.Numeric(12, 2), nullable=True),
        sa.Column('notify_email', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_address', sa.String(length=255), nullable=True),
        sa.Column('last_signal', sa.String(length=10), nullable=True),
        sa.Column('last_price', sa.Numeric(12, 4), nullable=True),
        sa.Column('last_evaluated_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_watchlist_items_symbol', 'watchlist_items', ['symbol'])


def downgrade() -> None:
    op.drop_index('ix_watchlist_items_symbol', table_name='watchlist_items')
    op.drop_table('watchlist_items')
