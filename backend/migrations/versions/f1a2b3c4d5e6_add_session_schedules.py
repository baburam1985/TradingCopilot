"""add session_schedules table and schedule columns on sessions

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
Create Date: 2026-04-03 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'session_schedules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('strategy', sa.String(length=100), nullable=False),
        sa.Column('strategy_params', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('capital', sa.Numeric(12, 2), nullable=False),
        sa.Column('mode', sa.String(length=20), nullable=False),
        sa.Column('stop_loss_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('take_profit_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('max_position_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('days_of_week', postgresql.JSONB(), nullable=False, server_default='[0,1,2,3,4]'),
        sa.Column('start_time_et', sa.Time(), nullable=False),
        sa.Column('stop_time_et', sa.Time(), nullable=True),
        sa.Column('auto_stop_daily_loss_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('auto_stop_max_trades', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_triggered_date', sa.Date(), nullable=True),
        sa.Column('last_session_id', sa.UUID(), nullable=True),
        sa.Column('last_run_status', sa.String(length=20), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['last_session_id'], ['sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_session_schedules_symbol', 'session_schedules', ['symbol'])
    op.create_index('ix_session_schedules_is_active', 'session_schedules', ['is_active'])

    # Add schedule linkage columns to sessions
    op.add_column('sessions', sa.Column('schedule_id', sa.UUID(), nullable=True))
    op.add_column('sessions', sa.Column('auto_started', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sessions', sa.Column('max_trades', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_sessions_schedule_id',
        'sessions', 'session_schedules',
        ['schedule_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_sessions_schedule_id', 'sessions', type_='foreignkey')
    op.drop_column('sessions', 'max_trades')
    op.drop_column('sessions', 'auto_started')
    op.drop_column('sessions', 'schedule_id')

    op.drop_index('ix_session_schedules_is_active', table_name='session_schedules')
    op.drop_index('ix_session_schedules_symbol', table_name='session_schedules')
    op.drop_table('session_schedules')
