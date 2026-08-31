"""Página pública da banca — a URL que o tipster manda para os assinantes."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.tip import Tip, TipStatus
from app.models.user import Bankroll


def publicar(session: Session, bankroll: Bankroll) -> Bankroll:
    bankroll.is_public = True
    session.commit()
    return bankroll


def add_tip(session: Session, bankroll: Bankroll, **kwargs) -> Tip:
    campos = {
        "bankroll_id": bankroll.id,
        "source": "bet365",
        "event": "Flamengo x Palmeiras",
        "market": "Mais de 2.5 gols",
        "odd": Decimal("2.00"),
        "stake": Decimal("300.00"),
        "stake_units": Decimal("2"),
        "currency": "BRL",
        "status": TipStatus.GREEN,
        "resolved_at": datetime.now(UTC),
        "published_at": datetime.now(UTC),
        **kwargs,
    }
    tip = Tip(**campos)
    session.add(tip)
    session.commit()
    return tip


def test_banca_publica_abre_sem_login(anon_client: TestClient, bankroll, db_session) -> None:
    publicar(db_session, bankroll)
    add_tip(db_session, bankroll)

    response = anon_client.get(f"/public/bankrolls/{bankroll.slug}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == bankroll.name
    assert body["stats"]["bets"] == 1
    assert len(body["tips"]) == 1


def test_banca_privada_responde_404(anon_client: TestClient, bankroll) -> None:
    """404, não 403: quem não pode ver não precisa saber que ela existe."""
    response = anon_client.get(f"/public/bankrolls/{bankroll.slug}")

    assert response.status_code == 404


def test_endereco_inexistente_responde_404(anon_client: TestClient) -> None:
    assert anon_client.get("/public/bankrolls/nao-existe").status_code == 404


def test_nada_em_reais_sai_na_pagina_publica(
    anon_client: TestClient, bankroll, db_session
) -> None:
    """O tamanho da banca de quem publica não é assunto dos assinantes."""
    publicar(db_session, bankroll)
    add_tip(db_session, bankroll, stake=Decimal("987.65"))

    corpo = anon_client.get(f"/public/bankrolls/{bankroll.slug}").text

    assert "987.65" not in corpo
    assert "brl" not in corpo.lower()
    assert "stake\":" not in corpo


def test_pagina_publica_nao_expoe_o_print_nem_os_envios(
    anon_client: TestClient, bankroll, db_session
) -> None:
    publicar(db_session, bankroll)
    add_tip(
        db_session,
        bankroll,
        raw_image_ref="print-com-meu-saldo.png",
        extraction_error="print cortado",
    )

    corpo = anon_client.get(f"/public/bankrolls/{bankroll.slug}").text

    assert "print-com-meu-saldo" not in corpo
    assert "extraction_error" not in corpo
    assert "messages" not in corpo


def test_unidades_e_resultado_aparecem(anon_client: TestClient, bankroll, db_session) -> None:
    publicar(db_session, bankroll)
    add_tip(db_session, bankroll)

    tip = anon_client.get(f"/public/bankrolls/{bankroll.slug}").json()["tips"][0]

    assert tip["status"] == "green"
    assert Decimal(tip["stake_units"]) == Decimal("2")
    assert Decimal(tip["odd"]) == Decimal("2.00")


def test_consolidado_publico_bate_com_o_privado(
    client: TestClient, anon_client: TestClient, bankroll, db_session
) -> None:
    publicar(db_session, bankroll)
    add_tip(db_session, bankroll)
    add_tip(db_session, bankroll, status=TipStatus.RED)

    privado = client.get(f"/bankrolls/{bankroll.id}/stats").json()
    publico = anon_client.get(f"/public/bankrolls/{bankroll.slug}").json()["stats"]

    assert publico["profit_units"] == privado["profit_units"]
    assert publico["roi"] == privado["roi"]
    assert publico["hit_rate"] == privado["hit_rate"]
    assert "profit_brl" not in publico


def test_despublicar_fecha_a_pagina(
    client: TestClient, anon_client: TestClient, bankroll, db_session
) -> None:
    publicar(db_session, bankroll)
    assert anon_client.get(f"/public/bankrolls/{bankroll.slug}").status_code == 200

    client.patch(f"/bankrolls/{bankroll.id}", json={"is_public": False})

    assert anon_client.get(f"/public/bankrolls/{bankroll.slug}").status_code == 404


def test_uma_banca_publica_nao_mostra_tips_da_outra(
    client: TestClient, anon_client: TestClient, bankroll, db_session
) -> None:
    publicar(db_session, bankroll)
    outra_id = client.post("/bankrolls", json={"name": "Outra banca"}).json()["id"]
    add_tip(db_session, bankroll, event="Da publicada")
    db_session.add(Tip(bankroll_id=outra_id, event="Da outra", currency="BRL"))
    db_session.commit()

    tips = anon_client.get(f"/public/bankrolls/{bankroll.slug}").json()["tips"]

    assert [t["event"] for t in tips] == ["Da publicada"]


def test_pagina_publica_nao_mostra_tip_em_revisao(
    anon_client: TestClient, bankroll, db_session
) -> None:
    """Rascunho não faz parte do histórico do grupo."""
    publicar(db_session, bankroll)
    add_tip(db_session, bankroll, event="Foi para o grupo")
    add_tip(db_session, bankroll, event="Ainda em revisão", published_at=None)

    body = anon_client.get(f"/public/bankrolls/{bankroll.slug}").json()

    assert [t["event"] for t in body["tips"]] == ["Foi para o grupo"]
    assert body["stats"]["bets"] == 1
