"""print da tip guardado no banco

Revision ID: b7620496145e
Revises: b1c4f0a92d3e
Create Date: 2026-08-29

Até aqui o print era lido pela IA e descartado — só o nome do arquivo ficava,
em ``raw_image_ref``. Guardando os bytes, a mensagem do grupo pode sair com a
imagem junto (``sendPhoto`` no Telegram).

No banco, e não em disco, para a imagem morrer junto com a tip descartada pelo
mesmo caminho do ``message_log``, sem rotina de limpeza de arquivo órfão.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7620496145e'
down_revision: Union[str, Sequence[str], None] = 'b1c4f0a92d3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tip', sa.Column('raw_image', sa.LargeBinary(), nullable=True))
    op.add_column('tip', sa.Column('raw_image_media_type', sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tip', 'raw_image_media_type')
    op.drop_column('tip', 'raw_image')
