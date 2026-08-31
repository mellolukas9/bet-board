"""stake_units na tip

Revision ID: b1c4f0a92d3e
Revises: ee6362b387bd
Create Date: 2026-08-27

O grupo aposta em unidades ("2u"), mas o print da casa só mostra reais. A
conversão é convenção do admin, então a coluna é nullable e preenchida na
revisão manual (PATCH /tips/{id}), não pela IA.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c4f0a92d3e'
down_revision: Union[str, Sequence[str], None] = 'ee6362b387bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tip', sa.Column('stake_units', sa.Numeric(precision=8, scale=2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tip', 'stake_units')
