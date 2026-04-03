"""add risk params to sessions

Revision ID: a1b2c3d4e5f6
Revises: c34986b5a436
Create Date: 2026-04-03 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c34986b5a436'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sessions', sa.Column('stop_loss_pct', sa.Numeric(precision=6, scale=2), nullable=True))
    op.add_column('sessions', sa.Column('take_profit_pct', sa.Numeric(precision=6, scale=2), nullable=True))
    op.add_column('sessions', sa.Column('max_position_pct', sa.Numeric(precision=6, scale=2), nullable=True))
    op.add_column('sessions', sa.Column('daily_max_loss_pct', sa.Numeric(precision=6, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('sessions', 'daily_max_loss_pct')
    op.drop_column('sessions', 'max_position_pct')
    op.drop_column('sessions', 'take_profit_pct')
    op.drop_column('sessions', 'stop_loss_pct')
