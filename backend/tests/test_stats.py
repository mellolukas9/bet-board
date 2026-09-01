"""Consolidação da banca: GET /stats."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.tip import Tip, TipStatus
from app.services import stats as stats_service


def add_tip(
    session: Session,
    bankroll,
    *,
    status: TipStatus,
    odd: str = "2.00",
    units: str = "1",
    stake: str = "100.00",
    resolved_at: datetime | None = None,
    published: bool = True,
) -> Tip:
    """Por padrão a tip nasce **publicada**: a banca só conta o que foi ao grupo."""
    tip = Tip(
        bankroll_id=bankroll.id,
        published_at=datetime.now(UTC) if published else None,
        source="bet365",
        event="Time A x Time B",
        market="Mais de 2.5 gols",
        odd=Decimal(odd),
        stake=Decimal(stake),
        stake_units=Decimal(units),
        currency="BRL",
        status=status,
        resolved_at=resolved_at or (datetime.now(UTC) if status is not TipStatus.PENDING else None),
    )
    session.add(tip)
    session.commit()
    return tip


def test_banca_vazia_nao_divide_por_zero(client, bankroll: TestClient) -> None:
    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert body["bets"] == 0
    assert Decimal(body["roi"]) == 0
    assert Decimal(body["hit_rate"]) == 0
    assert body["series"] == []


def test_lucro_em_unidades_e_em_reais(client, bankroll: TestClient, db_session) -> None:
    """Green de 2u @ 2.00 lucra 2u; red de 1u perde 1u. Sobram 1u de lucro."""
    add_tip(db_session, bankroll, status=TipStatus.GREEN, odd="2.00", units="2", stake="200.00")
    add_tip(db_session, bankroll, status=TipStatus.RED, odd="1.50", units="1", stake="100.00")

    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert body["green"] == 1
    assert body["red"] == 1
    assert Decimal(body["profit_units"]) == Decimal("1.00")
    assert Decimal(body["profit_brl"]) == Decimal("100.00")


def test_roi_e_taxa_de_acerto(client, bankroll: TestClient, db_session) -> None:
    """3u apostadas, 1u de lucro → ROI 33.33%; 1 green em 2 resolvidas → 50%."""
    add_tip(db_session, bankroll, status=TipStatus.GREEN, odd="2.00", units="2")
    add_tip(db_session, bankroll, status=TipStatus.RED, odd="1.50", units="1")

    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert Decimal(body["roi"]) == Decimal("33.33")
    assert Decimal(body["hit_rate"]) == Decimal("50.00")


def test_void_devolve_o_stake_e_fica_fora_do_roi(client, bankroll: TestClient, db_session) -> None:
    add_tip(db_session, bankroll, status=TipStatus.GREEN, odd="2.00", units="1")
    add_tip(db_session, bankroll, status=TipStatus.VOID, odd="3.00", units="5")

    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert body["void"] == 1
    assert body["settled"] == 1
    assert Decimal(body["profit_units"]) == Decimal("1.00")
    assert Decimal(body["staked_units"]) == Decimal("1.00")
    assert Decimal(body["roi"]) == Decimal("100.00")


def test_pendente_conta_como_aposta_mas_nao_como_lucro(
    client,
    bankroll: TestClient,
    db_session,
) -> None:
    add_tip(db_session, bankroll, status=TipStatus.PENDING, units="3")

    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert body["bets"] == 1
    assert body["pending"] == 1
    assert body["settled"] == 0
    assert Decimal(body["profit_units"]) == 0


def test_serie_acumula_por_dia(client, bankroll: TestClient, db_session) -> None:
    ontem = datetime.now(UTC) - timedelta(days=1)
    add_tip(db_session, bankroll, status=TipStatus.RED, units="1", resolved_at=ontem)
    add_tip(db_session, bankroll, status=TipStatus.GREEN, odd="2.00", units="2", resolved_at=ontem)
    add_tip(db_session, bankroll, status=TipStatus.GREEN, odd="2.00", units="1")

    series = client.get(f"/bankrolls/{bankroll.id}/stats").json()["series"]

    assert len(series) == 2
    assert series[0]["bets"] == 2
    assert Decimal(series[0]["cumulative_units"]) == Decimal("1.00")
    assert Decimal(series[1]["cumulative_units"]) == Decimal("2.00")


def test_filtro_por_periodo(client, bankroll: TestClient, db_session) -> None:
    """`since` corta pela data de entrada da tip no board."""
    add_tip(db_session, bankroll, status=TipStatus.GREEN, odd="2.00", units="1")
    amanha = (datetime.now(UTC) + timedelta(days=1)).date()

    body = client.get(
        f"/bankrolls/{bankroll.id}/stats", params={"since": amanha.isoformat()}
    ).json()

    assert body["bets"] == 0


def test_tip_sem_unidades_nao_estraga_a_conta(client, bankroll: TestClient, db_session) -> None:
    """Tip marcada como green antes da revisão vale 0 — não vira None nem 500."""
    tip = Tip(
        bankroll_id=bankroll.id,
        published_at=datetime.now(UTC),
        event="Time A x Time B",
        odd=Decimal("2.00"),
        status=TipStatus.GREEN,
        currency="BRL",
    )
    db_session.add(tip)
    db_session.commit()

    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert Decimal(body["profit_units"]) == 0
    assert stats_service.profit(tip, in_units=True) == 0


def test_ganho_da_tip(db_session, bankroll) -> None:
    """"Ganho" é o retorno bruto: stake x odd no green, nada no red."""
    green = add_tip(
        db_session, bankroll, status=TipStatus.GREEN, odd="1.85", stake="150.00", units="2"
    )
    red = add_tip(db_session, bankroll, status=TipStatus.RED, odd="1.85", stake="150.00", units="2")

    assert stats_service.returned_amount(green, in_units=False) == Decimal("277.50")
    assert stats_service.returned_amount(red, in_units=False) == 0


def test_tip_nao_publicada_fica_fora_da_banca(client: TestClient, bankroll, db_session) -> None:
    """Rascunho na fila de revisão não é aposta: ninguém do grupo a seguiu."""
    add_tip(db_session, bankroll, status=TipStatus.PENDING, published=False)

    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert body["bets"] == 0


def test_a_lista_da_banca_so_traz_o_publicado(
    client: TestClient, bankroll, db_session
) -> None:
    add_tip(db_session, bankroll, status=TipStatus.GREEN)
    add_tip(db_session, bankroll, status=TipStatus.PENDING, published=False)

    todas = client.get(f"/bankrolls/{bankroll.id}/tips").json()
    da_banca = client.get(f"/bankrolls/{bankroll.id}/tips?published=true").json()

    assert len(todas) == 2
    assert len(da_banca) == 1


# --- encerramento antecipado (cash out) ---------------------------------------


def encerrada(session: Session, bankroll, *, devolvido: str, **kwargs) -> Tip:
    """Uma tip encerrada: 100 apostados (1u) e ``devolvido`` de volta."""
    tip = add_tip(session, bankroll, status=TipStatus.CASHOUT, **kwargs)
    tip.cashout_amount = Decimal(devolvido)
    session.commit()
    return tip


def test_encerramento_com_lucro_entra_na_banca(client: TestClient, bankroll, db_session) -> None:
    """120 devolvidos sobre 100 apostados: +0,2u de lucro sobre 1u apostada."""
    encerrada(db_session, bankroll, devolvido="120.00")

    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert body["cashout"] == 1
    assert body["settled"] == 1
    assert Decimal(body["profit_units"]) == Decimal("0.20")
    assert Decimal(body["profit_brl"]) == Decimal("20.00")
    assert Decimal(body["roi"]) == Decimal("20.00")


def test_encerramento_com_prejuizo_entra_negativo(
    client: TestClient, bankroll, db_session
) -> None:
    encerrada(db_session, bankroll, devolvido="40.00")

    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert Decimal(body["profit_units"]) == Decimal("-0.60")
    assert Decimal(body["profit_brl"]) == Decimal("-60.00")


def test_ganho_do_encerramento_e_o_que_a_casa_devolveu(db_session, bankroll) -> None:
    """Nem o retorno cheio da odd, nem zero: o valor do cash out."""
    tip = encerrada(db_session, bankroll, devolvido="120.00", odd="3.00")

    assert stats_service.returned_amount(tip, in_units=False) == Decimal("120.00")
    assert stats_service.returned_amount(tip, in_units=True) == Decimal("1.20")


def test_encerramento_no_positivo_conta_como_acerto(
    client: TestClient, bankroll, db_session
) -> None:
    """Sair da aposta ganhando dinheiro é acerto para quem seguiu a tip."""
    encerrada(db_session, bankroll, devolvido="120.00")
    add_tip(db_session, bankroll, status=TipStatus.RED)

    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert body["settled"] == 2
    assert Decimal(body["hit_rate"]) == Decimal("50.00")


def test_encerramento_no_negativo_nao_conta_como_acerto(
    client: TestClient, bankroll, db_session
) -> None:
    encerrada(db_session, bankroll, devolvido="40.00")
    add_tip(db_session, bankroll, status=TipStatus.GREEN)

    body = client.get(f"/bankrolls/{bankroll.id}/stats").json()

    assert Decimal(body["hit_rate"]) == Decimal("50.00")


def test_encerramento_entra_na_curva_do_grafico(client: TestClient, bankroll, db_session) -> None:
    encerrada(db_session, bankroll, devolvido="150.00")

    series = client.get(f"/bankrolls/{bankroll.id}/stats").json()["series"]

    assert len(series) == 1
    assert Decimal(series[0]["cumulative_units"]) == Decimal("0.50")


def test_a_lista_da_banca_recorta_por_periodo(client: TestClient, bankroll, db_session) -> None:
    """O mesmo `since` do /stats, para lista e cartões falarem do mesmo período."""
    antiga = add_tip(db_session, bankroll, status=TipStatus.GREEN)
    antiga.created_at = datetime.now(UTC) - timedelta(days=40)
    db_session.commit()
    add_tip(db_session, bankroll, status=TipStatus.GREEN)

    desde = (datetime.now(UTC) - timedelta(days=7)).date().isoformat()
    tips = client.get(f"/bankrolls/{bankroll.id}/tips?published=true&since={desde}").json()

    assert len(tips) == 1
