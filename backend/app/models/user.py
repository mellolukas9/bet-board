"""Models do dono da conta e da banca.

A hierarquia é ``user`` → ``bankroll`` → ``tip``:

* **user** — o tipster que usa a ferramenta. Uma conta por cliente.
* **bankroll** — o grupo/banca que ele administra. É a unidade que importa: ela
  tem o canal do Telegram, as tips e a URL pública. Um mesmo tipster pode ter
  "VIP" e "Free" com canais diferentes, e os resultados de um não se misturam
  com os do outro.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(120))

    # Conta desativada não faz login, mas as bancas dela continuam existindo —
    # cancelar um cliente não pode apagar o histórico dele.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Quem administra o sistema (cria e desativa contas). É um papel só: ou a
    # conta é de um cliente, ou é sua. Papéis dentro da conta do cliente (dono ×
    # operador) ficam para quando algum cliente pedir.
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    bankrolls: Mapped[list["Bankroll"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        order_by="Bankroll.id",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class Bankroll(Base, TimestampMixin):
    """Uma banca/grupo: canal de envio, tips e página pública."""

    __tablename__ = "bankroll"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # O pedaço da URL pública (/b/<slug>). Único no sistema inteiro, não por
    # usuário: dois clientes não podem disputar o mesmo endereço.
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    description: Mapped[str | None] = mapped_column(Text)

    # Banca privada responde 404 na rota pública. O padrão é privada: publicar
    # os resultados é uma escolha, não o que acontece por descuido.
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- canais de envio, por banca ---
    # Ficavam no .env, o que amarrava o deploy a um único cliente. Guardados em
    # texto: quem alcança o banco normalmente alcança o .env do mesmo jeito, e
    # cifrar com uma chave que mora ao lado do dado protege pouco. Em troca, a
    # API **nunca** devolve o token inteiro — só os últimos dígitos.
    telegram_bot_token: Mapped[str | None] = mapped_column(String(255))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64))
    whatsapp_webhook_url: Mapped[str | None] = mapped_column(String(512))

    owner: Mapped[User] = relationship(back_populates="bankrolls")
    tips: Mapped[list["Tip"]] = relationship(  # noqa: F821
        back_populates="bankroll",
        cascade="all, delete-orphan",
        order_by="Tip.id",
    )

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    def __repr__(self) -> str:
        return f"<Bankroll id={self.id} slug={self.slug!r}>"
