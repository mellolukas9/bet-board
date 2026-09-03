"""Schemas Pydantic da tip."""

import re
from datetime import datetime
from decimal import Decimal
from typing import ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from app.models.tip import Channel, MessageStatus, TipStatus

#: "Dupla: ", "Múltipla - ", "Tripla — "… no começo do mercado.
_PREFIXO_DE_BILHETE = re.compile(
    r"^\s*(simples|dupla|tripla|qu[áa]drupla|m[úu]ltipla|acumulada)\s*[:\-–—]\s*",
    re.IGNORECASE,
)


def nome_do_evento(matches: list[str] | None) -> str | None:
    """O nome do evento a partir das partidas do bilhete.

    Um jogo vira o nome do jogo; daí para cima vira o tipo da aposta, que é
    como o grupo se refere a ela. Partidas repetidas contam uma vez só: uma
    múltipla com três seleções do mesmo jogo continua sendo aquele jogo.
    """
    if not matches:
        return None

    # dict.fromkeys tira repetição preservando a ordem de leitura do print
    unicas = [m.strip() for m in dict.fromkeys(matches) if m and m.strip()]

    if not unicas:
        return None
    if len(unicas) == 1:
        return unicas[0]
    if len(unicas) == 2:
        return "Dupla"
    if len(unicas) == 3:
        return "Tripla"
    return "Múltipla"


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
    matches: list[str] | None = Field(
        description=(
            "As partidas do bilhete, no formato 'Time A x Time B', uma por "
            "seleção e na ordem em que aparecem. Várias seleções da mesma "
            "partida repetem a partida. NUNCA use aqui o tipo da aposta "
            "('Dupla', 'Tripla', 'Múltipla'). null se não aparecer nenhuma."
        )
    )
    market: str | None = Field(
        description=(
            "Mercado apostado exatamente como no print (ex: 'Over 2.5 gols', "
            "'Vitória Time A', 'Ambas marcam'). Em múltipla, as seleções "
            "separadas por ' + '. NÃO comece com 'Dupla:', 'Tripla:' nem "
            "'Múltipla:' — o tipo da aposta já vai no evento. "
            "null se não aparecer."
        )
    )

    @field_validator("market")
    @classmethod
    def _sem_prefixo_de_bilhete(cls, valor: str | None) -> str | None:
        """Tira o "Dupla: " / "Múltipla - " da frente do mercado.

        O tipo da aposta já é o nome do evento; repeti-lo aqui deixa a mensagem
        do grupo com a mesma palavra em duas linhas seguidas. O prompt pede para
        não prefixar, mas modelo de visão varia — e a mensagem vai para o grupo.
        """
        if valor is None:
            return None
        return _PREFIXO_DE_BILHETE.sub("", valor).strip() or None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def event(self) -> str | None:
        """Nome do evento, derivado da quantidade de partidas.

        Contar é operação determinística: fazer em código, e não pedir à IA,
        tira uma fonte de variação de um campo que é obrigatório para publicar.
        O admin pode reescrever depois — o valor derivado é só o ponto de
        partida.

        É `computed_field` para sair na resposta da API sem entrar no schema
        que vai para a IA: structured outputs usam o schema de validação, e
        campo computado não aparece nele.
        """
        return nome_do_evento(self.matches)
    odd: float | None = Field(
        description=(
            "Cotação TOTAL do bilhete, em formato decimal (ex: 1.85). Em bilhete "
            "montado numa partida só ('Criar Aposta'), é a cotação do topo, ao "
            "lado do nome do jogo — nunca o produto das parciais de cada "
            "seleção. null se a total não aparecer."
        )
    )
    stake: float | None = Field(
        description=(
            "Valor apostado, apenas o número, sem símbolo de moeda (ex: 50.0). "
            "null se não aparecer — inclusive quando a caixa de aposta está "
            "vazia, esperando o valor."
        )
    )
    currency: str | None = Field(
        description="Código ISO da moeda (ex: BRL para R$). null se não der para inferir."
    )
    unreadable_reason: str | None = Field(
        description=(
            "Preencha SOMENTE se a IMAGEM não permitir a leitura (borrada, "
            "escura, texto cortado no meio, não é um print de aposta). Campo "
            "que simplesmente não aparece no print — stake, casa, cotação "
            "total — é null no campo dele e NÃO é motivo para preencher aqui. "
            "Descreva o problema em uma frase. null quando o print está legível."
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
    #: quanto a casa devolveu no encerramento antecipado, em reais
    cashout_amount: Decimal | None
    #: o mesmo valor em unidades, na proporção do stake (derivado, não gravado)
    cashout_units: Decimal | None
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
            "green (acertou), red (errou), void (anulada/devolvida), "
            "cashout (encerrada antes do fim) ou pending para voltar a tip "
            "para 'aguardando resultado'."
        )
    )
    cashout_amount: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Obrigatório em cashout: quanto a casa devolveu no encerramento, "
            "em reais. Acima do stake vira lucro; abaixo, prejuízo."
        ),
    )
    note: str | None = Field(
        default=None,
        max_length=500,
        description="Observação livre do admin, guardada junto do resultado.",
    )

    @model_validator(mode="after")
    def _cashout_tem_valor(self) -> "TipResult":
        """Encerrar sem dizer por quanto não é um resultado, é um campo em branco.

        A conta do encerramento é `devolvido - apostado`; sem o devolvido a tip
        entraria na banca valendo zero, calada.
        """
        if self.status is TipStatus.CASHOUT and self.cashout_amount is None:
            raise ValueError(
                "Informe por quanto a aposta foi encerrada (o valor devolvido "
                "pela casa, em reais)."
            )
        if self.status is not TipStatus.CASHOUT and self.cashout_amount is not None:
            raise ValueError(
                "O valor de encerramento só vale para o resultado 'encerrada'."
            )
        return self


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
