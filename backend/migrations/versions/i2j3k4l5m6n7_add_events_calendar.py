"""add events_calendar table

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
Create Date: 2026-04-03 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'i2j3k4l5m6n7'
down_revision: Union[str, None] = 'h1i2j3k4l5m6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'events_calendar',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=20), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=True),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('fetched_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_events_calendar_symbol_date', 'events_calendar', ['symbol', 'event_date'])
    op.create_index('ix_events_calendar_type_date', 'events_calendar', ['event_type', 'event_date'])


def downgrade() -> None:
    op.drop_index('ix_events_calendar_type_date', table_name='events_calendar')
    op.drop_index('ix_events_calendar_symbol_date', table_name='events_calendar')
    op.drop_table('events_calendar')
