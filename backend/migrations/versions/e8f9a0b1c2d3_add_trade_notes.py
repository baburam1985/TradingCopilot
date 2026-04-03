"""add trade_notes table

Revision ID: e8f9a0b1c2d3
Revises: e7f8a9b0c1d2
Create Date: 2026-04-03 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'trade_notes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('trade_id', sa.UUID(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['trade_id'], ['paper_trades.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_trade_notes_trade_id', 'trade_notes', ['trade_id'])


def downgrade() -> None:
    op.drop_index('ix_trade_notes_trade_id', table_name='trade_notes')
    op.drop_table('trade_notes')
