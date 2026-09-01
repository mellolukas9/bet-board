"""encerramento antecipado da aposta (cash out)

Revision ID: a2e8b6c4d951
Revises: f1a4c7d9e320
Create Date: 2026-09-01

A aposta pode sair antes do fim do jogo, pelo valor que a casa oferece na hora
— e esse valor tanto pode estar acima do apostado (lucro) quanto abaixo
(prejuízo). Não é green nem red: são dois fatos diferentes, e juntá-los faria a
taxa de acerto mentir nos dois sentidos.

Daí as duas mudanças: um status `cashout` no enum e a coluna com o valor
devolvido, em reais. As unidades saem da proporção com o stake, em Python
(`Tip.cashout_units`), e por isso não viram coluna.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a2e8b6c4d951'
down_revision: Union[str, Sequence[str], None] = 'f1a4c7d9e320'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Os valores do enum antes desta revisão — o downgrade recria o tipo com eles.
STATUS_ANTERIORES = ('pending', 'green', 'red', 'void')


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'tip', sa.Column('cashout_amount', sa.Numeric(precision=12, scale=2), nullable=True)
    )

    # No SQLite (a suíte) o status é VARCHAR e não há tipo a alterar.
    if op.get_bind().dialect.name != 'postgresql':
        return

    # ADD VALUE não pode rodar dentro da transação da migração em todo servidor
    # suportado; o autocommit_block resolve isso sem depender da versão.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tip_status ADD VALUE IF NOT EXISTS 'cashout'")


def downgrade() -> None:
    """Downgrade schema.

    Tip encerrada vira `void`: é o resultado que sobra mais próximo — aposta
    resolvida que não foi acerto nem erro. O saldo dela some junto com a coluna,
    então este caminho **muda número de banca**, não só schema.
    """
    op.execute("UPDATE tip SET status = 'void' WHERE status = 'cashout'")
    op.drop_column('tip', 'cashout_amount')

    if op.get_bind().dialect.name != 'postgresql':
        return

    # Postgres não remove valor de enum: o tipo é recriado sem ele e a coluna
    # migrada por texto.
    valores = ", ".join(f"'{v}'" for v in STATUS_ANTERIORES)
    op.execute("ALTER TYPE tip_status RENAME TO tip_status_old")
    op.execute(f"CREATE TYPE tip_status AS ENUM ({valores})")
    op.execute(
        "ALTER TABLE tip ALTER COLUMN status TYPE tip_status "
        "USING status::text::tip_status"
    )
    op.execute("DROP TYPE tip_status_old")
