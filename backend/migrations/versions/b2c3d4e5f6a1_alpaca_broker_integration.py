"""alpaca broker integration: extend mode column, add alpaca_order_id to trades

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-04-03 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend mode column to accommodate "alpaca_paper" and "alpaca_live"
    op.alter_column('sessions', 'mode',
                    existing_type=sa.String(length=10),
                    type_=sa.String(length=20),
                    existing_nullable=False)
    # Track Alpaca order IDs on trades created by AlpacaExecutor
    op.add_column('paper_trades',
                  sa.Column('alpaca_order_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('paper_trades', 'alpaca_order_id')
    op.alter_column('sessions', 'mode',
                    existing_type=sa.String(length=20),
                    type_=sa.String(length=10),
                    existing_nullable=False)
