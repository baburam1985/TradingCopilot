"""add close_summaries and user_streaks tables

Revision ID: h1i2j3k4l5m6
Revises: g8h9i0j1k2l3
Create Date: 2026-04-03 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'h1i2j3k4l5m6'
down_revision: Union[str, None] = 'g8h9i0j1k2l3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_streaks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('longest_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_trading_date', sa.String(length=10), nullable=True),
        sa.Column('milestone_badges', postgresql.JSONB(), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'close_summaries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('generated_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('trading_date', sa.String(length=10), nullable=False),
        sa.Column('total_pnl', sa.Numeric(12, 4), nullable=False, server_default='0'),
        sa.Column('trade_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('win_rate', sa.Numeric(6, 4), nullable=False, server_default='0'),
        sa.Column('max_drawdown_pct', sa.Numeric(8, 4), nullable=False, server_default='0'),
        sa.Column('pattern_analysis', postgresql.JSONB(), nullable=True),
        sa.Column('tomorrow_preview', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_close_summaries_session_id', 'close_summaries', ['session_id'])
    op.create_index('ix_close_summaries_trading_date', 'close_summaries', ['trading_date'])


def downgrade() -> None:
    op.drop_index('ix_close_summaries_trading_date', table_name='close_summaries')
    op.drop_index('ix_close_summaries_session_id', table_name='close_summaries')
    op.drop_table('close_summaries')
    op.drop_table('user_streaks')
