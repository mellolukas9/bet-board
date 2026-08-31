"""Assistente de configuração do Telegram.

Cada teste aqui corresponde a uma das armadilhas reais de configurar um bot de
canal — as mesmas que custaram uma sessão de debug quando o envio começou a
falhar com "need administrator rights".
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.services import telegram_setup

TOKEN = "1234567890:AAHtokenDeTeste"


def fake_client(rotas: dict[str, dict]) -> httpx.Client:
    """Cliente que responde por método da Bot API, sem tocar na rede."""

    def handler(request: httpx.Request) -> httpx.Response:
        metodo = request.url.path.rsplit("/", 1)[-1]
        if metodo not in rotas:
            return httpx.Response(404, json={"ok": False, "description": "Not Found"})
        return httpx.Response(200, json=rotas[metodo])

    return httpx.Client(transport=httpx.MockTransport(handler))


BOT_OK = {"ok": True, "result": {"id": 1234567890, "username": "betboard_bot", "first_name": "Bet"}}
CANAL_OK = {"ok": True, "result": {"id": -100123, "title": "Bet Board Tips", "type": "channel"}}


def test_tudo_certo() -> None:
    with fake_client(
        {
            "getMe": BOT_OK,
            "getChat": CANAL_OK,
            "getChatMember": {
                "ok": True,
                "result": {"status": "administrator", "can_post_messages": True},
            },
        }
    ) as client:
        d = telegram_setup.diagnose(TOKEN, "-100123", client=client)

    assert d.ok
    assert d.bot_username == "betboard_bot"
    assert d.canal_titulo == "Bet Board Tips"
    assert d.pode_publicar
    assert d.problemas == []


def test_token_errado_para_no_primeiro_passo() -> None:
    """Sem token válido, falar do canal só confundiria."""
    with fake_client({"getMe": {"ok": False, "description": "Unauthorized"}}) as client:
        d = telegram_setup.diagnose(TOKEN, "-100123", client=client)

    assert not d.ok
    assert not d.token_valido
    assert not d.canal_encontrado
    assert "token" in d.problemas[0].lower()


def test_sem_canal_informado_pede_a_deteccao() -> None:
    with fake_client({"getMe": BOT_OK}) as client:
        d = telegram_setup.diagnose(TOKEN, None, client=client)

    assert d.token_valido
    assert not d.ok
    assert "Detectar canais" in d.problemas[0]


def test_bot_fora_do_canal() -> None:
    """O erro cru é "chat not found" — a mensagem diz o que fazer."""
    with fake_client(
        {"getMe": BOT_OK, "getChat": {"ok": False, "description": "chat not found"}}
    ) as client:
        d = telegram_setup.diagnose(TOKEN, "-100123", client=client)

    assert not d.canal_encontrado
    assert "adicionado ao canal" in d.problemas[0]
    assert "betboard_bot" in d.problemas[0]


def test_bot_no_canal_mas_sem_ser_admin() -> None:
    """A causa exata do "need administrator rights" no envio."""
    with fake_client(
        {
            "getMe": BOT_OK,
            "getChat": CANAL_OK,
            "getChatMember": {"ok": True, "result": {"status": "member"}},
        }
    ) as client:
        d = telegram_setup.diagnose(TOKEN, "-100123", client=client)

    assert d.canal_encontrado
    assert not d.bot_e_admin
    assert not d.ok
    assert "Administradores" in d.problemas[0]


def test_admin_sem_permissao_de_publicar() -> None:
    with fake_client(
        {
            "getMe": BOT_OK,
            "getChat": CANAL_OK,
            "getChatMember": {
                "ok": True,
                "result": {"status": "administrator", "can_post_messages": False},
            },
        }
    ) as client:
        d = telegram_setup.diagnose(TOKEN, "-100123", client=client)

    assert d.bot_e_admin
    assert not d.pode_publicar
    assert "Publicar mensagens" in d.problemas[0]


def test_grupo_nao_exige_can_post_messages() -> None:
    """`can_post_messages` só existe em canal; em grupo, ser admin basta."""
    with fake_client(
        {
            "getMe": BOT_OK,
            "getChat": {"ok": True, "result": {"id": -1, "title": "Grupo", "type": "supergroup"}},
            "getChatMember": {"ok": True, "result": {"status": "administrator"}},
        }
    ) as client:
        d = telegram_setup.diagnose(TOKEN, "-1", client=client)

    assert d.ok


def test_detecta_canais_sem_repetir() -> None:
    updates = {
        "ok": True,
        "result": [
            {"channel_post": {"chat": {"id": -100123, "title": "Tips VIP", "type": "channel"}}},
            {"channel_post": {"chat": {"id": -100123, "title": "Tips VIP", "type": "channel"}}},
            {"message": {"chat": {"id": -456, "title": "Grupo Free", "type": "supergroup"}}},
            # conversa direta com uma pessoa não é destino de tip
            {"message": {"chat": {"id": 999, "type": "private", "username": "lucas"}}},
        ],
    }
    with fake_client({"getUpdates": updates}) as client:
        chats = telegram_setup.detect_chats(TOKEN, client=client)

    assert [c.chat_id for c in chats] == ["-100123", "-456"]
    assert chats[0].title == "Tips VIP"


def test_detectar_com_token_invalido_estoura() -> None:
    with fake_client({"getUpdates": {"ok": False, "description": "Unauthorized"}}) as client:
        with pytest.raises(telegram_setup.TelegramSetupError, match="recusou o token"):
            telegram_setup.detect_chats(TOKEN, client=client)


def test_falha_de_rede_vira_erro_proprio() -> None:
    def cai(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    with httpx.Client(transport=httpx.MockTransport(cai)) as client:
        with pytest.raises(telegram_setup.TelegramSetupError, match="rede"):
            telegram_setup.check_token(TOKEN, client=client)


def test_id_do_bot_sai_do_token_sem_ir_na_rede() -> None:
    assert telegram_setup._bot_id("1234567890:AAH") == "1234567890"


# --- pela API -----------------------------------------------------------------


def test_rota_de_teste_usa_o_que_ainda_nao_foi_salvo(
    client: TestClient, bankroll, monkeypatch
) -> None:
    """O cliente testa o token que acabou de digitar, antes de salvar."""
    vistos: dict = {}

    def espiao(token, chat_id, **kwargs):
        vistos["token"] = token
        vistos["chat_id"] = chat_id
        return telegram_setup.Diagnostico(ok=True, token_valido=True)

    monkeypatch.setattr("app.api.routes.bankrolls.telegram_setup.diagnose", espiao)

    response = client.post(
        f"/bankrolls/{bankroll.id}/telegram/test",
        json={"bot_token": "novo:token", "chat_id": "-999"},
    )

    assert response.status_code == 200
    assert vistos == {"token": "novo:token", "chat_id": "-999"}


def test_rota_de_teste_cai_no_que_esta_salvo(client: TestClient, bankroll, monkeypatch) -> None:
    client.patch(
        f"/bankrolls/{bankroll.id}",
        json={"telegram_bot_token": "salvo:token", "telegram_chat_id": "-111"},
    )
    vistos: dict = {}

    def espiao(token, chat_id, **kwargs):
        vistos.update(token=token, chat_id=chat_id)
        return telegram_setup.Diagnostico()

    monkeypatch.setattr("app.api.routes.bankrolls.telegram_setup.diagnose", espiao)

    client.post(f"/bankrolls/{bankroll.id}/telegram/test", json={})

    assert vistos == {"token": "salvo:token", "chat_id": "-111"}


def test_detectar_sem_token_e_400(client: TestClient, bankroll) -> None:
    response = client.post(f"/bankrolls/{bankroll.id}/telegram/detect", json={})

    assert response.status_code == 400
    assert "token" in response.json()["detail"]


def test_detectar_sem_resultado_devolve_a_dica(client: TestClient, bankroll, monkeypatch) -> None:
    """Lista vazia é o caso comum da primeira vez — precisa dizer o que fazer."""
    monkeypatch.setattr(
        "app.api.routes.bankrolls.telegram_setup.detect_chats", lambda token, **k: []
    )

    body = client.post(
        f"/bankrolls/{bankroll.id}/telegram/detect", json={"bot_token": TOKEN}
    ).json()

    assert body["chats"] == []
    assert "mande qualquer mensagem" in body["dica"]


def test_assistente_exige_login(anon_client: TestClient, bankroll) -> None:
    assert (
        anon_client.post(f"/bankrolls/{bankroll.id}/telegram/test", json={}).status_code == 401
    )
