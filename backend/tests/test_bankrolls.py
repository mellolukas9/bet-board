"""Bancas: criação, endereço público, configuração e isolamento entre contas."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.models.tip import Tip, TipStatus
from app.models.user import User
from app.services import bankrolls as bankrolls_service
from tests.conftest import login_as


def test_cria_banca_e_deriva_o_endereco(client: TestClient) -> None:
    response = client.post("/bankrolls", json={"name": "Vip Peçanha"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Vip Peçanha"
    assert body["slug"] == "vip-pecanha"
    assert body["is_public"] is False


def test_banca_nasce_privada(client: TestClient) -> None:
    """Publicar os resultados é uma escolha, não o padrão."""
    assert client.post("/bankrolls", json={"name": "Nova"}).json()["is_public"] is False


def test_endereco_repetido_ganha_sufixo(client: TestClient) -> None:
    client.post("/bankrolls", json={"name": "Vip"})

    segunda = client.post("/bankrolls", json={"name": "Vip"}).json()

    assert segunda["slug"] == "vip-2"


def test_endereco_acompanha_o_nome_ao_renomear(client: TestClient, bankroll) -> None:
    """`/b/<slug>` é sempre o nome: renomear a banca move o endereço junto."""
    body = client.patch(f"/bankrolls/{bankroll.id}", json={"name": "Vip Peçanha"}).json()

    assert body["name"] == "Vip Peçanha"
    assert body["slug"] == "vip-pecanha"


def test_renomear_para_o_mesmo_nome_mantem_o_endereco(client: TestClient, bankroll) -> None:
    """Sem isto, salvar duas vezes viraria banca-de-teste-2."""
    body = client.patch(f"/bankrolls/{bankroll.id}", json={"name": bankroll.name}).json()

    assert body["slug"] == bankroll.slug


def test_mudar_so_a_descricao_nao_mexe_no_endereco(client: TestClient, bankroll) -> None:
    body = client.patch(f"/bankrolls/{bankroll.id}", json={"description": "Oi"}).json()

    assert body["slug"] == bankroll.slug


def test_endereco_nao_e_editavel_pela_api(client: TestClient, bankroll) -> None:
    """A regra mora num lugar só: mandar slug não muda nada."""
    criada = client.post(
        "/bankrolls", json={"name": "Vip", "slug": "endereco-inventado"}
    ).json()
    assert criada["slug"] == "vip"

    editada = client.patch(
        f"/bankrolls/{bankroll.id}", json={"slug": "outro-inventado"}
    ).json()
    assert editada["slug"] == bankroll.slug


def test_nome_reservado_ganha_sufixo(client: TestClient) -> None:
    """Uma banca chamada "Login" não pode virar /b/login."""
    body = client.post("/bankrolls", json={"name": "Login"}).json()

    assert body["slug"] == "login-2"


def test_nome_sem_letras_cai_num_endereco_utilizavel(client: TestClient) -> None:
    """Nome só de símbolos não derruba nada — cai no fallback, que também
    respeita a lista de reservados (daí o sufixo)."""
    body = client.post("/bankrolls", json={"name": "!!! ###"}).json()

    assert body["slug"] == "banca-2"
    assert body["slug"] not in bankrolls_service.SLUGS_RESERVADOS


def test_nome_muito_curto_vira_endereco_valido(client: TestClient) -> None:
    """O endereço tem mínimo de 3 caracteres; o nome não precisa ter."""
    body = client.post("/bankrolls", json={"name": "Vi"}).json()

    assert len(body["slug"]) >= 3


def test_nome_repetido_entre_contas_nao_colide(
    client: TestClient, outro_usuario: User, db_session
) -> None:
    """O endereço é único no sistema, não por conta."""
    bankrolls_service.create_bankroll(db_session, outro_usuario, name="Vip")
    db_session.commit()

    body = client.post("/bankrolls", json={"name": "Vip"}).json()

    assert body["slug"] == "vip-2"


def test_lista_so_as_minhas_bancas(
    client: TestClient, bankroll, outro_usuario: User, db_session
) -> None:
    bankrolls_service.create_bankroll(db_session, outro_usuario, name="Banca alheia")
    db_session.commit()

    slugs = [b["slug"] for b in client.get("/bankrolls").json()]

    assert slugs == [bankroll.slug]


def test_banca_de_outra_conta_responde_404(
    client: TestClient, outro_usuario: User, db_session
) -> None:
    """404, não 403: um 403 já confirmaria que a banca existe."""
    alheia = bankrolls_service.create_bankroll(db_session, outro_usuario, name="Alheia")
    db_session.commit()

    assert client.get(f"/bankrolls/{alheia.id}").status_code == 404
    assert client.patch(f"/bankrolls/{alheia.id}", json={"name": "Roubada"}).status_code == 404
    assert client.get(f"/bankrolls/{alheia.id}/tips").status_code == 404
    assert client.get(f"/bankrolls/{alheia.id}/stats").status_code == 404


def test_tip_de_outra_conta_responde_404(
    client: TestClient, outro_usuario: User, db_session
) -> None:
    alheia = bankrolls_service.create_bankroll(db_session, outro_usuario, name="Alheia")
    db_session.add(Tip(bankroll_id=alheia.id, event="Segredo x Alheio", currency="BRL"))
    db_session.commit()
    tip_id = db_session.query(Tip).one().id

    assert client.get(f"/tips/{tip_id}").status_code == 404
    assert client.patch(f"/tips/{tip_id}", json={"stake_units": "2"}).status_code == 404
    assert client.post(f"/tips/{tip_id}/result", json={"status": "green"}).status_code == 404
    assert client.delete(f"/tips/{tip_id}").status_code == 404


def test_cada_conta_ve_a_sua_banca(
    client: TestClient, bankroll, outro_usuario: User, db_session
) -> None:
    outra = bankrolls_service.create_bankroll(db_session, outro_usuario, name="Do intruso")
    db_session.commit()

    login_as(client, outro_usuario, "outra-senha")

    slugs = [b["slug"] for b in client.get("/bankrolls").json()]
    assert slugs == [outra.slug]


def test_configura_o_telegram(client: TestClient, bankroll) -> None:
    body = client.patch(
        f"/bankrolls/{bankroll.id}",
        json={"telegram_bot_token": "1234567890:AAHsecretoAqui", "telegram_chat_id": "-100123"},
    ).json()

    assert body["telegram_configured"] is True
    assert body["telegram_chat_id"] == "-100123"


def test_token_do_bot_nunca_volta_inteiro(client: TestClient, bankroll) -> None:
    """O token dá poder de publicar no canal — ele entra e não sai mais."""
    token = "1234567890:AAHsegredoQueNaoPodeVazar"
    resposta = client.patch(
        f"/bankrolls/{bankroll.id}", json={"telegram_bot_token": token}
    ).json()

    assert token not in str(resposta)
    assert resposta["telegram_bot_token_hint"] == "1234567890:…azar"


def test_apagar_o_token_desconecta_o_canal(client: TestClient, bankroll) -> None:
    client.patch(f"/bankrolls/{bankroll.id}", json={"telegram_bot_token": "123:ABC"})

    body = client.patch(f"/bankrolls/{bankroll.id}", json={"telegram_bot_token": ""}).json()

    assert body["telegram_configured"] is False
    assert body["telegram_bot_token_hint"] is None


def test_apaga_banca_vazia(client: TestClient, bankroll) -> None:
    assert client.delete(f"/bankrolls/{bankroll.id}").status_code == 204
    assert client.get(f"/bankrolls/{bankroll.id}").status_code == 404


def test_recusa_apagar_banca_com_tips(client: TestClient, bankroll, db_session) -> None:
    """Histórico não some num clique."""
    db_session.add(Tip(bankroll_id=bankroll.id, event="Time A x Time B", currency="BRL"))
    db_session.commit()

    response = client.delete(f"/bankrolls/{bankroll.id}")

    assert response.status_code == 409
    assert "1 tip" in response.json()["detail"]


def test_apagar_banca_leva_as_tips_junto(db_session, bankroll) -> None:
    """No banco o cascade existe; a rota é que se recusa a usá-lo sem querer."""
    db_session.add(
        Tip(
            bankroll_id=bankroll.id,
            event="Time A x Time B",
            status=TipStatus.GREEN,
            currency="BRL",
        )
    )
    db_session.commit()

    bankrolls_service.delete_bankroll(db_session, bankroll)
    db_session.commit()

    assert db_session.query(Tip).count() == 0


def test_tips_de_bancas_diferentes_nao_se_misturam(
    client: TestClient, bankroll, db_session
) -> None:
    outra = client.post("/bankrolls", json={"name": "Segunda"}).json()
    db_session.add(Tip(bankroll_id=bankroll.id, event="Da primeira", currency="BRL"))
    db_session.add(Tip(bankroll_id=outra["id"], event="Da segunda", currency="BRL"))
    db_session.commit()

    primeira = client.get(f"/bankrolls/{bankroll.id}/tips").json()
    segunda = client.get(f"/bankrolls/{outra['id']}/tips").json()

    assert [t["event"] for t in primeira] == ["Da primeira"]
    assert [t["event"] for t in segunda] == ["Da segunda"]


def test_stats_contam_so_a_banca_pedida(client: TestClient, bankroll, db_session) -> None:
    outra = client.post("/bankrolls", json={"name": "Segunda"}).json()
    agora = datetime.now(UTC)
    db_session.add(Tip(bankroll_id=bankroll.id, event="A", currency="BRL", published_at=agora))
    db_session.add(Tip(bankroll_id=outra["id"], event="B", currency="BRL", published_at=agora))
    db_session.add(Tip(bankroll_id=outra["id"], event="C", currency="BRL", published_at=agora))
    db_session.commit()

    assert client.get(f"/bankrolls/{bankroll.id}/stats").json()["bets"] == 1
    assert client.get(f"/bankrolls/{outra['id']}/stats").json()["bets"] == 2
