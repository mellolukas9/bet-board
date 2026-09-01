"""Schemas da consolidação da banca (painel)."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class BankrollPoint(BaseModel):
    """Um dia da curva da banca."""

    date: date
    bets: int
    profit_units: Decimal
    profit_brl: Decimal
    cumulative_units: Decimal
    cumulative_brl: Decimal


class BankrollStats(BaseModel):
    """O que os cartões e o gráfico do painel mostram.

    Lucro e ROI saem em unidades (como o grupo aposta) e em reais. `void` não
    entra no ROI nem na taxa de acerto: aposta anulada devolve o stake.
    `cashout` (encerrada antes do fim) entra nos dois — o dinheiro já mudou de
    lado — e conta como acerto quando o saldo dela foi positivo.
    """

    bankroll_id: int
    bets: int
    settled: int
    pending: int
    green: int
    red: int
    void: int
    #: encerradas antes do fim (cash out)
    cashout: int
    needs_review: int

    staked_units: Decimal
    staked_brl: Decimal
    profit_units: Decimal
    profit_brl: Decimal
    #: lucro / total apostado, em % (unidades)
    roi: Decimal
    #: resolvidas no positivo / resolvidas, em %
    hit_rate: Decimal

    series: list[BankrollPoint]
