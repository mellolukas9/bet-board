"""Consolidação de resultados da banca.

Alimenta o painel: os cartões (apostas, lucro, ROI, acerto) e a curva de
evolução da banca. Os números saem em **unidades** — é como o grupo aposta — e
em reais, para quem quiser ver o valor cheio.

Conta **só tip publicada**. O que ainda está na fila de revisão não foi apostado
por ninguém do grupo; incluí-lo inflaria o histórico com rascunho.

O cálculo roda em Python, não em SQL agregado, de propósito: o volume é de um
grupo de tips (centenas por mês, não milhões), e assim a mesma fórmula vale em
Postgres e no SQLite dos testes, sem dialeto pelo meio.
"""

from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tz import dia_local, fim_do_dia, inicio_do_dia
from app.models.tip import Tip, TipStatus

ZERO = Decimal("0")

#: Resultados que entram no cálculo de lucro. `void` (anulada) devolve o stake,
#: então não é acerto nem erro — fica de fora do ROI e da taxa de acerto.
#:
#: `cashout` (encerrada antes do fim) entra: o dinheiro já mudou de lado, e o
#: saldo dela é tão real quanto o de um green.
SETTLED = (TipStatus.GREEN, TipStatus.RED, TipStatus.CASHOUT)


def returned_amount(tip: Tip, *, in_units: bool) -> Decimal:
    """Quanto voltou da aposta ("Ganho"): stake x odd no green, 0 no red.

    No encerramento antecipado quem diz é a casa: voltou o valor do cash out,
    nem o retorno cheio nem zero.
    """
    stake = _stake(tip, in_units=in_units)
    if tip.status is TipStatus.GREEN:
        return stake * _odd(tip)
    if tip.status is TipStatus.RED:
        return ZERO
    if tip.status is TipStatus.CASHOUT:
        return _cashout(tip, in_units=in_units)
    # pendente ou anulada: o dinheiro ainda é (ou voltou a ser) do apostador
    return stake if tip.status is TipStatus.VOID else ZERO


def profit(tip: Tip, *, in_units: bool) -> Decimal:
    """Lucro da tip: ``stake x (odd - 1)`` no green, ``-stake`` no red, 0 no resto.

    O encerramento é a diferença entre o que voltou e o que foi apostado — por
    isso ele pode dar lucro **ou** prejuízo, sem ser green nem red.
    """
    stake = _stake(tip, in_units=in_units)
    if tip.status is TipStatus.GREEN:
        return stake * (_odd(tip) - 1)
    if tip.status is TipStatus.RED:
        return -stake
    if tip.status is TipStatus.CASHOUT:
        return _cashout(tip, in_units=in_units) - stake
    return ZERO


def bankroll_summary(
    session: Session,
    *,
    bankroll_id: int,
    since: date | None = None,
    until: date | None = None,
) -> dict:
    """Números consolidados + a série diária acumulada para o gráfico.

    ``since``/``until`` filtram pela data em que a tip entrou no board
    (``created_at``), inclusive nas duas pontas.
    """
    tips = _tips_in_range(session, bankroll_id=bankroll_id, since=since, until=until)

    counts = {status: 0 for status in TipStatus}
    for tip in tips:
        counts[tip.status] += 1

    settled = [t for t in tips if t.status in SETTLED]
    staked_units = sum((_stake(t, in_units=True) for t in settled), ZERO)
    staked_brl = sum((_stake(t, in_units=False) for t in settled), ZERO)
    profit_units = sum((profit(t, in_units=True) for t in settled), ZERO)
    profit_brl = sum((profit(t, in_units=False) for t in settled), ZERO)

    return {
        "bankroll_id": bankroll_id,
        "bets": len(tips),
        "settled": len(settled),
        "pending": counts[TipStatus.PENDING],
        "green": counts[TipStatus.GREEN],
        "red": counts[TipStatus.RED],
        "void": counts[TipStatus.VOID],
        "cashout": counts[TipStatus.CASHOUT],
        "needs_review": sum(1 for t in tips if t.needs_review),
        "staked_units": _q(staked_units),
        "staked_brl": _q(staked_brl),
        "profit_units": _q(profit_units),
        "profit_brl": _q(profit_brl),
        "roi": _percent(profit_units, staked_units),
        "hit_rate": _percent(Decimal(_hits(settled)), Decimal(len(settled))),
        "series": _daily_series(settled),
    }


def _hits(settled: list[Tip]) -> int:
    """Quantas apostas resolvidas terminaram no positivo.

    Green é acerto por definição. Encerramento entra pelo saldo: sair da aposta
    ganhando dinheiro é um acerto para quem seguiu a tip, e sair perdendo não é
    — chamar todo cash out de erro puniria justamente a saída que deu lucro.
    """
    return sum(
        1
        for t in settled
        if t.status is TipStatus.GREEN
        or (t.status is TipStatus.CASHOUT and profit(t, in_units=True) > 0)
    )


def _daily_series(settled: list[Tip]) -> list[dict]:
    """Um ponto por dia com resultado, com o acumulado da banca.

    A data é a da resolução (é quando o dinheiro entra ou sai); tip resolvida
    antes desta coluna existir cai no ``created_at``. O dia é o de São Paulo:
    resolver às 22h não pode empurrar o ponto para o dia seguinte.
    """
    by_day: OrderedDict[date, dict] = OrderedDict()

    for tip in sorted(settled, key=_settled_at):
        day = dia_local(_settled_at(tip))
        point = by_day.setdefault(
            day, {"date": day, "bets": 0, "profit_units": ZERO, "profit_brl": ZERO}
        )
        point["bets"] += 1
        point["profit_units"] += profit(tip, in_units=True)
        point["profit_brl"] += profit(tip, in_units=False)

    cumulative_units = ZERO
    cumulative_brl = ZERO
    series = []
    for point in by_day.values():
        cumulative_units += point["profit_units"]
        cumulative_brl += point["profit_brl"]
        series.append(
            {
                "date": point["date"],
                "bets": point["bets"],
                "profit_units": _q(point["profit_units"]),
                "profit_brl": _q(point["profit_brl"]),
                "cumulative_units": _q(cumulative_units),
                "cumulative_brl": _q(cumulative_brl),
            }
        )
    return series


def _tips_in_range(
    session: Session, *, bankroll_id: int, since: date | None, until: date | None
) -> list[Tip]:
    # Só o que foi para o grupo entra na banca. Tip em revisão ainda é
    # rascunho: ninguém apostou nela, e ela não tem resultado a marcar.
    stmt = select(Tip).where(
        Tip.bankroll_id == bankroll_id, Tip.published_at.is_not(None)
    )
    # As bordas são meia-noite e meia-noite menos um instante **em São Paulo**,
    # não em UTC: senão o filtro de "hoje" começa às 21h de ontem.
    if since is not None:
        stmt = stmt.where(Tip.created_at >= inicio_do_dia(since))
    if until is not None:
        stmt = stmt.where(Tip.created_at <= fim_do_dia(until))
    return list(session.scalars(stmt.order_by(Tip.id)))


def _settled_at(tip: Tip) -> datetime:
    return tip.resolved_at or tip.created_at


def _stake(tip: Tip, *, in_units: bool) -> Decimal:
    value = tip.stake_units if in_units else tip.stake
    return ZERO if value is None else Decimal(value)


def _cashout(tip: Tip, *, in_units: bool) -> Decimal:
    """O valor devolvido no encerramento, em reais ou em unidades."""
    value = tip.cashout_units if in_units else tip.cashout_amount
    return ZERO if value is None else Decimal(value)


def _odd(tip: Tip) -> Decimal:
    return ZERO if tip.odd is None else Decimal(tip.odd)


def _percent(part: Decimal, whole: Decimal) -> Decimal:
    """Percentual com 2 casas; 0 quando não há base (evita divisão por zero)."""
    return ZERO if whole == 0 else _q(part / whole * 100)


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))
