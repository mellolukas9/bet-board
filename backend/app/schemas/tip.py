"""Schemas Pydantic da tip."""

from datetime import datetime
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.tip import Channel, MessageStatus, TipStatus


class TipExtracted(BaseModel):
    """Saída da IA de visão ao ler o print.

    Todos os campos são opcionais: um print ilegível ou incompleto não pode
    quebrar o pipeline — ele vira uma tip marcada para revisão manual.

    Este schema é enviado à IA como JSON Schema, então mantenha-o plano e sem
    restrições numéricas (não suportadas por structured outputs). Os campos são
    obrigatórios porém anuláveis de propósito: a IA precisa se pronunciar sobre
    cada um (com ``null`` quando não achou), em vez de omiti-los silenciosamente.
    """

    source: str | None = Field(
        description="Casa de apostas ou origem da tip (ex: Bet365, Betano). null se não aparecer."
    )
    event: str | None = Field(
        description=(
            "Evento/partida, no formato 'Time A x Time B' quando aplicável. "
            "null se não aparecer."
        )
    )
    market: str | None = Field(
        description=(
            "Mercado apostado exatamente como no print (ex: 'Over 2.5 gols', "
            "'Vitória Time A', 'Ambas marcam'). null se não aparecer."
        )
    )
    odd: float | None = Field(
        description="Cotação em formato decimal (ex: 1.85). null se não aparecer."
    )
    stake: float | None = Field(
        description=(
            "Valor apostado, apenas o número, sem símbolo de moeda (ex: 50.0). "
            "null se não aparecer."
        )
    )
    currency: str | None = Field(
        description="Código ISO da moeda (ex: BRL para R$). null se não der para inferir."
    )
    unreadable_reason: str | None = Field(
        description=(
            "Preencha SOMENTE se o print não permitir a leitura (borrado, cortado, "
            "não é um print de aposta). Descreva o problema em uma frase. "
            "null quando o print está legível."
        )
    )

    # Campos que precisam estar presentes para a tip ser publicável sem revisão.
    REQUIRED_FIELDS: ClassVar[tuple[str, ...]] = (
        "source",
        "event",
        "market",
        "odd",
        "stake",
    )

    @property
    def missing_fields(self) -> list[str]:
        return [f for f in self.REQUIRED_FIELDS if getattr(self, f) is None]

    @property
    def is_complete(self) -> bool:
        return self.unreadable_reason is None and not self.missing_fields


class MessageLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: Channel
    status: MessageStatus
    sent_at: datetime | None
    error: str | None


class TipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str | None
    event: str | None
    market: str | None
    odd: Decimal | None
    stake: Decimal | None
    stake_units: Decimal | None
    currency: str
    link: str | None
    raw_image_ref: str | None
    status: TipStatus
    needs_review: bool
    extraction_error: str | None
    extracted_at: datetime | None
    #: null enquanto a tip não foi para o grupo — é o que libera marcar resultado
    published_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    messages: list[MessageLogRead] = []


class TipUpdate(BaseModel):
    """Correção manual de uma tip mal lida (PATCH /tips/{id}).

    Só os campos enviados são alterados — o resto fica como está. É aqui que o
    admin informa ``stake_units``: o print traz o valor em reais, e a conversão
    para unidades é convenção dele, não dado da casa de apostas.
    """

    source: str | None = None
    event: str | None = None
    market: str | None = None
    odd: Decimal | None = None
    stake: Decimal | None = None
    stake_units: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    link: str | None = Field(
        default=None,
        max_length=512,
        description="Link da aposta na casa. Vai na mensagem do grupo.",
    )
    status: TipStatus | None = None
    needs_review: bool | None = None

    @field_validator("link")
    @classmethod
    def _link_utilizavel(cls, valor: str | None) -> str | None:
        """Recusa link que não abre.

        A mensagem vai para o grupo inteiro; um "bet365.com/abc" sem esquema
        vira texto morto no Telegram, e o assinante só descobre clicando.
        String vazia limpa o campo.
        """
        if valor is None:
            return None

        limpo = valor.strip()
        if not limpo:
            return None
        if not limpo.startswith(("http://", "https://")):
            raise ValueError("O link precisa começar com http:// ou https://.")
        return limpo


class TipResult(BaseModel):
    """Corpo do POST /tips/{id}/result — o admin diz se deu green ou red.

    Decisão de 31/08: **nada de API esportiva nesta fase**. Quem confere o
    resultado é o próprio admin, pelo painel; a Fase 2 (validação automática)
    entra depois, e vai gravar o mesmo campo por outro caminho.
    """

    status: TipStatus = Field(
        description=(
            "green (acertou), red (errou), void (anulada/devolvida) ou pending "
            "para voltar a tip para 'aguardando resultado'."
        )
    )
    note: str | None = Field(
        default=None,
        max_length=500,
        description="Observação livre do admin, guardada junto do resultado.",
    )


class TipPublish(BaseModel):
    """Corpo do POST /tips/{id}/publish."""

    force: bool = Field(
        default=False,
        description=(
            "Republica uma tip que já foi enviada. Sem isto, reenviar é recusado "
            "para não duplicar mensagem no grupo."
        ),
    )


class TipPublishResponse(BaseModel):
    """Resultado da publicação: a tip, o texto enviado e o status por canal."""

    tip: TipRead
    message: str
    channels: dict[Channel, MessageStatus]
