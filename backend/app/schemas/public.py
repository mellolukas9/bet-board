"""Schemas da página pública da banca.

Tudo aqui é **em unidades**. O valor em reais fica de fora de propósito: a
página é prova de performance para os assinantes do grupo, e o tamanho da banca
de quem publica não é assunto deles. Também não saem daqui o print original, o
erro de leitura nem o log de envio — nada que só interesse a quem administra.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.tip import TipStatus


class PublicTip(BaseModel):
    """Uma aposta, como um assinante do grupo vê."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event: str | None
    market: str | None
    source: str | None
    odd: Decimal | None
    stake_units: Decimal | None
    #: o que voltou de um encerramento antecipado, em unidades (null nas demais)
    cashout_units: Decimal | None
    status: TipStatus
    created_at: datetime
    resolved_at: datetime | None


class PublicPoint(BaseModel):
    date: date
    bets: int
    profit_units: Decimal
    cumulative_units: Decimal


class PublicStats(BaseModel):
    bets: int
    settled: int
    pending: int
    green: int
    red: int
    void: int
    cashout: int

    staked_units: Decimal
    profit_units: Decimal
    roi: Decimal
    hit_rate: Decimal

    series: list[PublicPoint]


class PublicBankroll(BaseModel):
    """A página inteira numa resposta só — é uma tela, não vale duas idas."""

    name: str
    slug: str
    description: str | None
    owner_name: str | None
    since: datetime | None
    stats: PublicStats
    tips: list[PublicTip]
