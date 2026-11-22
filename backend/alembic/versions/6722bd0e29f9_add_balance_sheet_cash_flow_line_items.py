"""add_balance_sheet_cash_flow_line_items

Revision ID: 6722bd0e29f9
Revises: 6ce003bdab84
Create Date: 2026-11-21 23:23:11.068866

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6722bd0e29f9'
down_revision: Union[str, Sequence[str], None] = '6ce003bdab84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - adds granular balance sheet & cash flow line items."""
    op.add_column('financial_statements', sa.Column('current_assets', sa.Numeric(precision=18, scale=2), nullable=True))
    op.add_column('financial_statements', sa.Column('current_liabilities', sa.Numeric(precision=18, scale=2), nullable=True))
    op.add_column('financial_statements', sa.Column('inventory', sa.Numeric(precision=18, scale=2), nullable=True))
    op.add_column('financial_statements', sa.Column('free_cash_flow', sa.Numeric(precision=18, scale=2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('financial_statements', 'free_cash_flow')
    op.drop_column('financial_statements', 'inventory')
    op.drop_column('financial_statements', 'current_liabilities')
    op.drop_column('financial_statements', 'current_assets')
