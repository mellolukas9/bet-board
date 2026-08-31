"""conta de administrador do sistema

Revision ID: d5b2c8e1a730
Revises: c3a1d5e7f204
Create Date: 2026-08-31

Separa dois papéis que até aqui eram um só: quem administra uma **banca** (o
cliente) e quem administra o **sistema** (cria e desativa contas).

A conta que existia antes desta revision vira administradora: numa instalação
de um cliente só, ela era as duas coisas — e tirar o acesso de quem já usava
seria uma regressão, não uma migração.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5b2c8e1a730'
down_revision: Union[str, Sequence[str], None] = 'c3a1d5e7f204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'user',
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Quem já estava lá administrava tudo; promove a primeira conta para que o
    # painel de administração não nasça inacessível.
    op.execute(
        'UPDATE "user" SET is_superuser = true '
        'WHERE id = (SELECT min(id) FROM "user")'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user', 'is_superuser')
