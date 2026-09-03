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
    session: Session,
    bankroll,
    *,
    status: TipStatus = TipStatus.PENDING,
    published: bool = True,
    stake: Decimal | None = Decimal("150.00"),
    **kwargs,
) -> Tip:
    """Publicada por padrão: só tip que foi ao grupo tem resultado a marcar."""
    tip = Tip(
        bankroll_id=bankroll.id,
        published_at=datetime.now(UTC) if published else None,
        source="bet365",
        event="Flamengo x Palmeiras",
        market="Mais de 2.5 gols",
        odd=Decimal("1.85"),
        stake=stake,
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


def test_tip_nao_publicada_nao_aceita_resultado(client: TestClient, db_session, bankroll) -> None:
    """A confirmação de green/red só existe depois que a tip foi para o grupo."""
    tip = make_tip(db_session, bankroll, published=False)

    response = client.post(f"/tips/{tip.id}/result", json={"status": "green"})

    assert response.status_code == 409
    assert "publique-a" in response.json()["detail"].lower()


def test_patch_de_status_em_tip_nao_publicada_e_recusado(
    client: TestClient, db_session, bankroll
) -> None:
    """O PATCH aceita `status`; vale a mesma regra, senão seria a porta dos fundos."""
    tip = make_tip(db_session, bankroll, published=False)

    assert client.patch(f"/tips/{tip.id}", json={"status": "green"}).status_code == 409


def test_corrigir_outros_campos_continua_valendo_sem_publicar(
    client: TestClient, db_session, bankroll
) -> None:
    """A fila de revisão não pode travar: só o resultado depende da publicação."""
    tip = make_tip(db_session, bankroll, published=False)

    response = client.patch(f"/tips/{tip.id}", json={"stake_units": "3"})

    assert response.status_code == 200


# --- encerramento antecipado (cash out) ---------------------------------------


def test_encerramento_com_lucro(client: TestClient, db_session, bankroll) -> None:
    """Saiu da aposta por mais do que apostou: 180 devolvidos sobre 150 apostados."""
    tip = make_tip(db_session, bankroll)

    response = client.post(
        f"/tips/{tip.id}/result",
        json={"status": "cashout", "cashout_amount": "180.00"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cashout"
    assert Decimal(body["cashout_amount"]) == Decimal("180")
    # 180/150 do stake -> 1,2x as 2 unidades apostadas
    assert Decimal(body["cashout_units"]) == Decimal("2.4")
    assert body["resolved_at"] is not None


def test_encerramento_com_prejuizo(client: TestClient, db_session, bankroll) -> None:
    """Encerrar não é sinônimo de lucro — a casa também oferece menos que o stake."""
    tip = make_tip(db_session, bankroll)

    body = client.post(
        f"/tips/{tip.id}/result",
        json={"status": "cashout", "cashout_amount": "60.00"},
    ).json()

    assert Decimal(body["cashout_units"]) == Decimal("0.8")


def test_encerramento_aceita_virgula_decimal(client: TestClient, db_session, bankroll) -> None:
    """O valor é digitado no teclado brasileiro, na mesma tela da odd."""
    tip = make_tip(db_session, bankroll)

    body = client.post(
        f"/tips/{tip.id}/result",
        json={"status": "cashout", "cashout_amount": "180,00"},
    ).json()

    assert Decimal(body["cashout_amount"]) == Decimal("180")
    assert Decimal(body["cashout_units"]) == Decimal("2.4")


def test_encerramento_exige_o_valor_devolvido(client: TestClient, db_session, bankroll) -> None:
    tip = make_tip(db_session, bankroll)

    response = client.post(f"/tips/{tip.id}/result", json={"status": "cashout"})

    assert response.status_code == 422
    assert "encerrada" in response.text


def test_valor_de_encerramento_nao_vale_para_os_outros_resultados(
    client: TestClient, db_session, bankroll
) -> None:
    """Green com valor de encerramento seria um resultado contando duas histórias."""
    tip = make_tip(db_session, bankroll)

    response = client.post(
        f"/tips/{tip.id}/result", json={"status": "green", "cashout_amount": "180.00"}
    )

    assert response.status_code == 422


def test_encerramento_sem_valor_da_aposta_e_recusado(
    client: TestClient, db_session, bankroll
) -> None:
    """Sem o stake em reais não há proporção — e a tip entraria na banca valendo nada."""
    tip = make_tip(db_session, bankroll, stake=None)

    response = client.post(
        f"/tips/{tip.id}/result",
        json={"status": "cashout", "cashout_amount": "180.00"},
    )

    assert response.status_code == 409
    assert "valor da aposta" in response.json()["detail"]


def test_desfazer_o_encerramento_limpa_o_valor(client: TestClient, db_session, bankroll) -> None:
    """Voltar para pendente apaga o número: ele descreve um resultado que sumiu."""
    tip = make_tip(db_session, bankroll)
    client.post(
        f"/tips/{tip.id}/result",
        json={"status": "cashout", "cashout_amount": "180.00"},
    )

    body = client.post(f"/tips/{tip.id}/result", json={"status": "pending"}).json()

    assert body["status"] == "pending"
    assert body["cashout_amount"] is None
    assert body["cashout_units"] is None


def test_marcar_green_depois_do_encerramento_apaga_o_valor(
    client: TestClient, db_session, bankroll
) -> None:
    tip = make_tip(db_session, bankroll)
    client.post(
        f"/tips/{tip.id}/result",
        json={"status": "cashout", "cashout_amount": "180.00"},
    )

    body = client.post(f"/tips/{tip.id}/result", json={"status": "green"}).json()

    assert body["status"] == "green"
    assert body["cashout_amount"] is None
