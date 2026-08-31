"""Resultado informado pelo admin: POST /tips/{id}/result.

Nesta fase não existe validação automática — quem diz se deu green ou red é o
dono do grupo, pelo painel.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.tip import Tip, TipStatus


def make_tip(
    session: Session, bankroll, *, status: TipStatus = TipStatus.PENDING, **kwargs
) -> Tip:
    tip = Tip(
        bankroll_id=bankroll.id,
        source="bet365",
        event="Flamengo x Palmeiras",
        market="Mais de 2.5 gols",
        odd=Decimal("1.85"),
        stake=Decimal("150.00"),
        stake_units=Decimal("2"),
        currency="BRL",
        status=status,
        **kwargs,
    )
    session.add(tip)
    session.commit()
    return tip


@pytest.mark.parametrize("resultado", ["green", "red", "void"])
def test_admin_marca_o_resultado(client, bankroll: TestClient, db_session, resultado: str) -> None:
    tip = make_tip(db_session, bankroll)

    response = client.post(f"/tips/{tip.id}/result", json={"status": resultado})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == resultado
    assert body["resolved_at"] is not None


def test_resultado_manual_fica_marcado_como_manual(
    client,
    bankroll: TestClient,
    db_session,
) -> None:
    """`result_raw` diz de onde veio — a Fase 2 vai gravar o mesmo campo por outro caminho."""
    tip = make_tip(db_session, bankroll)

    client.post(f"/tips/{tip.id}/result", json={"status": "green", "note": "2x0 no primeiro tempo"})

    db_session.refresh(tip)
    assert tip.result_raw["source"] == "manual"
    assert tip.result_raw["note"] == "2x0 no primeiro tempo"


def test_voltar_para_pending_desfaz_o_resultado(client, bankroll: TestClient, db_session) -> None:
    """Clique errado acontece — o admin precisa conseguir desmarcar."""
    tip = make_tip(db_session, bankroll, status=TipStatus.GREEN, resolved_at=datetime.now(UTC))

    body = client.post(f"/tips/{tip.id}/result", json={"status": "pending"}).json()

    assert body["status"] == "pending"
    assert body["resolved_at"] is None
    db_session.refresh(tip)
    assert tip.result_raw is None


def test_patch_de_status_tambem_carimba_a_resolucao(
    client,
    bankroll: TestClient,
    db_session,
) -> None:
    """O PATCH aceita status desde a 1.5; ele passa pela mesma regra do result."""
    tip = make_tip(db_session, bankroll)

    body = client.patch(f"/tips/{tip.id}", json={"status": "red"}).json()

    assert body["status"] == "red"
    assert body["resolved_at"] is not None


def test_resultado_em_tip_inexistente_e_404(client: TestClient) -> None:
    assert client.post("/tips/999/result", json={"status": "green"}).status_code == 404


def test_status_invalido_e_recusado(client, bankroll: TestClient, db_session) -> None:
    tip = make_tip(db_session, bankroll)

    assert client.post(f"/tips/{tip.id}/result", json={"status": "meio-green"}).status_code == 422


def test_result_exige_login(anon_client, bankroll: TestClient, db_session) -> None:
    tip = make_tip(db_session, bankroll)

    assert anon_client.post(f"/tips/{tip.id}/result", json={"status": "green"}).status_code == 401
