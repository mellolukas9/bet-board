"""link da aposta na casa

Revision ID: f1a4c7d9e320
Revises: e7f3a9c2b118
Create Date: 2026-08-31

O "compartilhar bilhete" da Bet365/Betano. Com ele na mensagem, o assinante
abre a mesma aposta em vez de remontá-la campo a campo.

Vem do admin, nunca da IA: o link não está no print. Como `stake_units`, é
informado na revisão — mas, ao contrário dele, não é obrigatório para publicar:
tip sem link continua saindo, só sem o atalho.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1a4c7d9e320'
down_revision: Union[str, Sequence[str], None] = 'e7f3a9c2b118'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tip', sa.Column('link', sa.String(length=512), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tip', 'link')
