"""Models da tip e do log de mensagens."""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class TipStatus(enum.StrEnum):
    PENDING = "pending"
    GREEN = "green"
    RED = "red"
    VOID = "void"


class Channel(enum.StrEnum):
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"


class MessageStatus(enum.StrEnum):
    SENT = "sent"
    FAILED = "failed"


class Tip(Base, TimestampMixin):
    __tablename__ = "tip"

    id: Mapped[int] = mapped_column(primary_key=True)

    # A tip pertence a uma banca, não ao sistema: é ela que define em qual canal
    # a mensagem sai e em qual página pública o resultado aparece.
    bankroll_id: Mapped[int] = mapped_column(
        ForeignKey("bankroll.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Os campos da tip são nullable de propósito: quando a IA não consegue ler o
    # print, a tip é persistida mesmo assim e vai para a fila de revisão manual.
    source: Mapped[str | None] = mapped_column(String(120))
    event: Mapped[str | None] = mapped_column(String(255))
    market: Mapped[str | None] = mapped_column(String(255))
    odd: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    stake: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL", nullable=False)

    # O grupo aposta em unidades ("2u"), mas o print só mostra reais — a conversão
    # é convenção do admin, não dado do print. Por isso o campo é preenchido na
    # revisão (PATCH), não pela IA, e a tip não é publicável enquanto for null.
    stake_units: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    raw_image_ref: Mapped[str | None] = mapped_column(String(512))

    # O print em si, para ir junto com a mensagem no grupo. Fica no banco (e não
    # em disco) porque assim ele morre junto com a tip descartada, pelo mesmo
    # cascade do message_log — sem rotina de limpeza de arquivo órfão.
    raw_image: Mapped[bytes | None] = mapped_column(LargeBinary)
    raw_image_media_type: Mapped[str | None] = mapped_column(String(64))

    status: Mapped[TipStatus] = mapped_column(
        Enum(TipStatus, name="tip_status", values_callable=lambda e: [m.value for m in e]),
        default=TipStatus.PENDING,
        nullable=False,
        index=True,
    )

    # --- controle de revisão manual (Fase 1) ---
    needs_review: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    extraction_error: Mapped[str | None] = mapped_column(Text)

    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- resultado (Fase 2) ---
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_raw: Mapped[dict | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))

    bankroll: Mapped["Bankroll"] = relationship(back_populates="tips")  # noqa: F821

    messages: Mapped[list["MessageLog"]] = relationship(
        back_populates="tip",
        cascade="all, delete-orphan",
        order_by="MessageLog.id",
    )

    def __repr__(self) -> str:
        return f"<Tip id={self.id} status={self.status.value} event={self.event!r}>"


class MessageLog(Base, TimestampMixin):
    __tablename__ = "message_log"
    __table_args__ = (Index("ix_message_log_tip_channel", "tip_id", "channel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tip_id: Mapped[int] = mapped_column(
        ForeignKey("tip.id", ondelete="CASCADE"), nullable=False
    )

    channel: Mapped[Channel] = mapped_column(
        Enum(Channel, name="message_channel", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    status: Mapped[MessageStatus] = mapped_column(
        Enum(
            MessageStatus,
            name="message_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    tip: Mapped[Tip] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<MessageLog tip={self.tip_id} {self.channel.value}={self.status.value}>"
