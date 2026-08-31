"""contas de usuário e bancas; a tip passa a pertencer a uma banca

Revision ID: c3a1d5e7f204
Revises: b7620496145e
Create Date: 2026-08-31

Até aqui o sistema atendia **um** tipster: o admin vinha do ``.env`` e o canal
do Telegram também. Isso amarrava cada deploy a um cliente.

Agora a hierarquia é ``user`` → ``bankroll`` → ``tip``. A banca é a unidade que
importa: ela tem o canal, as tips e a URL pública.

Migração dos dados existentes: se já havia tips (ou um admin configurado no
ambiente), esta revision cria a conta e a banca correspondentes a partir do
``.env`` e move as tips para lá. Ninguém perde o login nem o histórico ao
atualizar; a instalação nova sobe vazia e a conta nasce pela CLI
(``python -m app.cli create-user``).
"""
import os
import re
import unicodedata
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3a1d5e7f204'
down_revision: Union[str, Sequence[str], None] = 'b7620496145e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)

    op.create_table(
        'bankroll',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('telegram_bot_token', sa.String(length=255), nullable=True),
        sa.Column('telegram_chat_id', sa.String(length=64), nullable=True),
        sa.Column('whatsapp_webhook_url', sa.String(length=512), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bankroll_user_id'), 'bankroll', ['user_id'])
    op.create_index(op.f('ix_bankroll_slug'), 'bankroll', ['slug'], unique=True)

    # Nullable primeiro: as tips que já existem ainda não têm dona.
    op.add_column('tip', sa.Column('bankroll_id', sa.Integer(), nullable=True))

    _migrar_dados_existentes()

    op.create_index(op.f('ix_tip_bankroll_id'), 'tip', ['bankroll_id'])
    op.create_foreign_key(
        'fk_tip_bankroll_id', 'tip', 'bankroll', ['bankroll_id'], ['id'], ondelete='CASCADE'
    )
    op.alter_column('tip', 'bankroll_id', nullable=False)


def downgrade() -> None:
    """Downgrade schema.

    Volta a um sistema de um cliente só. As tips continuam lá, mas a informação
    de qual banca era cada uma se perde — assim como as contas.
    """
    op.drop_constraint('fk_tip_bankroll_id', 'tip', type_='foreignkey')
    op.drop_index(op.f('ix_tip_bankroll_id'), table_name='tip')
    op.drop_column('tip', 'bankroll_id')

    op.drop_index(op.f('ix_bankroll_slug'), table_name='bankroll')
    op.drop_index(op.f('ix_bankroll_user_id'), table_name='bankroll')
    op.drop_table('bankroll')

    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_table('user')


# --- migração dos dados -------------------------------------------------------


def _migrar_dados_existentes() -> None:
    """Cria a conta e a banca do dono atual e move as tips órfãs para ela.

    Só roda quando há o que preservar: tips no banco, ou um admin configurado no
    ambiente. Instalação nova não ganha usuário nenhum — a conta nasce pela CLI.
    """
    conn = op.get_bind()

    tips_orfas = conn.execute(sa.text('SELECT count(*) FROM tip')).scalar() or 0
    senha_hash = _senha_do_ambiente()

    if not tips_orfas and senha_hash is None:
        return

    if senha_hash is None:
        # Há tips mas nenhuma credencial no .env: a conta é criada mesmo assim
        # (o histórico não pode ficar sem dono) com uma senha impossível. Quem
        # for usá-la define a senha com `python -m app.cli set-password`.
        senha_hash = 'sem-senha-definida'

    username = (os.environ.get('ADMIN_USERNAME') or 'admin').strip().lower()

    user_id = conn.execute(
        sa.text(
            'INSERT INTO "user" (username, password_hash, name, is_active) '
            'VALUES (:username, :password_hash, :name, true) RETURNING id'
        ),
        {'username': username, 'password_hash': senha_hash, 'name': None},
    ).scalar_one()

    nome_banca = os.environ.get('DEFAULT_BANKROLL_NAME') or 'Minha banca'
    bankroll_id = conn.execute(
        sa.text(
            'INSERT INTO bankroll '
            '(user_id, name, slug, is_public, telegram_bot_token, telegram_chat_id, '
            ' whatsapp_webhook_url) '
            'VALUES (:user_id, :name, :slug, false, :token, :chat_id, :webhook) '
            'RETURNING id'
        ),
        {
            'user_id': user_id,
            'name': nome_banca,
            'slug': _slugify(nome_banca) or 'minha-banca',
            # o canal que estava no .env passa a ser o canal desta banca
            'token': os.environ.get('TELEGRAM_BOT_TOKEN') or None,
            'chat_id': os.environ.get('TELEGRAM_CHAT_ID') or None,
            'webhook': os.environ.get('WHATSAPP_WEBHOOK_URL') or None,
        },
    ).scalar_one()

    conn.execute(
        sa.text('UPDATE tip SET bankroll_id = :bankroll_id WHERE bankroll_id IS NULL'),
        {'bankroll_id': bankroll_id},
    )


def _senha_do_ambiente() -> str | None:
    """O hash do admin que estava no ``.env``, ou ``None`` se não havia um."""
    hash_configurado = (os.environ.get('ADMIN_PASSWORD_HASH') or '').strip()
    if hash_configurado:
        return hash_configurado

    senha = os.environ.get('ADMIN_PASSWORD') or ''
    if not senha:
        return None

    # import tardio: a migration não deve puxar a app inteira quando não precisa
    from app.core.security import hash_password

    return hash_password(senha)


def _slugify(texto: str) -> str:
    sem_acento = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-zA-Z0-9]+', '-', sem_acento).strip('-').lower()[:64]
