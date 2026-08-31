"""a tip guarda quando foi publicada

Revision ID: e7f3a9c2b118
Revises: d5b2c8e1a730
Create Date: 2026-08-31

"Foi publicada" era deduzido varrendo o `message_log` atrás de um envio com
sucesso. Vira coluna por dois motivos: dá para filtrar em SQL (a banca passa a
mostrar só o que foi para o grupo) e o fato sobrevive a uma limpeza de log.

O backfill lê o próprio `message_log`, então nenhuma tip já publicada some da
banca ao atualizar.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7f3a9c2b118'
down_revision: Union[str, Sequence[str], None] = 'd5b2c8e1a730'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tip', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_tip_published_at'), 'tip', ['published_at'])

    # A data é a do primeiro envio que deu certo. `sent_at` pode ser nulo em
    # registro antigo, daí o COALESCE com a criação da linha do log.
    op.execute(
        """
        UPDATE tip SET published_at = (
            SELECT min(COALESCE(m.sent_at, m.created_at))
            FROM message_log m
            WHERE m.tip_id = tip.id AND m.status = 'sent'
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema.

    O dado não se perde: ele continua dedutível do `message_log`, que é de onde
    veio.
    """
    op.drop_index(op.f('ix_tip_published_at'), table_name='tip')
    op.drop_column('tip', 'published_at')
