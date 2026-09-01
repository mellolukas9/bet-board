"""Login, renovação da sessão e isolamento entre contas."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.security import AuthError, decode_access_token, hash_password, verify_password
from app.models.user import User
from app.services import users as users_service
from tests.conftest import ADMIN_CREDENTIALS, TEST_ITERATIONS


def test_hash_de_senha_confere_a_senha_certa():
    stored = hash_password("uma-senha-qualquer", iterations=TEST_ITERATIONS)

    assert verify_password("uma-senha-qualquer", stored)
    assert not verify_password("outra-senha", stored)


def test_hash_de_senha_nao_repete_o_valor():
    """Salt aleatório: a mesma senha nunca gera o mesmo hash."""
    assert hash_password("igual", iterations=TEST_ITERATIONS) != hash_password(
        "igual", iterations=TEST_ITERATIONS
    )


def test_hash_malformado_nao_quebra():
    """Hash torto no banco vira senha errada, não um 500."""
    assert not verify_password("qualquer", "isto-nao-e-um-hash")


def test_login_devolve_token(anon_client: TestClient, user: User):
    response = anon_client.post("/auth/login", json=ADMIN_CREDENTIALS)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["username"] == user.username
    # o sub do token é o id da conta, não o nome
    assert decode_access_token(body["access_token"]).subject == str(user.id)


def test_login_ignora_maiusculas_no_usuario(anon_client: TestClient, user: User):
    response = anon_client.post(
        "/auth/login", json={"username": "TIPSTER", "password": ADMIN_CREDENTIALS["password"]}
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "credenciais",
    [
        {"username": "tipster", "password": "errada"},
        {"username": "nao-existe", "password": "senha-de-teste"},
    ],
)
def test_login_recusa_credencial_errada(anon_client: TestClient, user: User, credenciais: dict):
    response = anon_client.post("/auth/login", json=credenciais)

    assert response.status_code == 401
    assert "inválidos" in response.json()["detail"]


def test_conta_desativada_nao_entra(anon_client: TestClient, user: User, db_session):
    user.is_active = False
    db_session.commit()

    response = anon_client.post("/auth/login", json=ADMIN_CREDENTIALS)

    assert response.status_code == 401
    assert "desativada" in response.json()["detail"]


def test_desativar_conta_derruba_o_token_na_hora(client: TestClient, user: User, db_session):
    """A conta é relida a cada requisição — não se espera o token expirar."""
    assert client.get("/auth/me").status_code == 200

    user.is_active = False
    db_session.commit()

    assert client.get("/auth/me").status_code == 401


def test_me_traz_a_conta_e_as_bancas(client: TestClient, bankroll):
    response = client.get("/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "tipster"
    assert [b["slug"] for b in body["bankrolls"]] == [bankroll.slug]


def test_login_carimba_o_ultimo_acesso(anon_client: TestClient, user: User, db_session):
    assert user.last_login_at is None

    anon_client.post("/auth/login", json=ADMIN_CREDENTIALS)

    db_session.refresh(user)
    assert user.last_login_at is not None


def test_rota_de_bancas_exige_token(anon_client: TestClient):
    response = anon_client.get("/bankrolls")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_rota_de_tips_exige_token(anon_client: TestClient, bankroll):
    assert anon_client.get(f"/bankrolls/{bankroll.id}/tips").status_code == 401


def test_rota_de_stats_exige_token(anon_client: TestClient, bankroll):
    assert anon_client.get(f"/bankrolls/{bankroll.id}/stats").status_code == 401


def test_token_adulterado_e_recusado(anon_client: TestClient):
    response = anon_client.get(
        "/bankrolls", headers={"Authorization": "Bearer nao.e.um.token"}
    )

    assert response.status_code == 401


def test_health_continua_publico(anon_client: TestClient):
    """O frontend consulta o /health antes de ter token."""
    assert anon_client.get("/health").status_code == 200


def test_token_expirado_e_recusado(monkeypatch):
    """Janela negativa simula a sessão vencida sem esperar o relógio."""
    from app.config import get_settings
    from app.core.security import create_access_token

    settings = get_settings()
    monkeypatch.setattr(settings, "auth_idle_timeout_minutes", -1)
    token, _ = create_access_token("1")

    with pytest.raises(AuthError, match="expirada"):
        decode_access_token(token)


def test_usuario_inexistente_custa_o_mesmo_que_senha_errada(db_session):
    """O tempo de resposta não pode denunciar quais contas existem.

    Não dá para cronometrar isso de forma estável num teste; o que dá para
    garantir é que o caminho do usuário inexistente **também** verifica uma
    senha, em vez de sair antes.
    """
    chamadas: list[str] = []
    original = users_service.verify_password

    def espiao(password: str, stored: str) -> bool:
        chamadas.append(stored)
        return original(password, stored)

    users_service.verify_password = espiao
    try:
        with pytest.raises(AuthError):
            users_service.authenticate(db_session, "nao-existe", "qualquer")
    finally:
        users_service.verify_password = original

    assert len(chamadas) == 1


# --- sessão que cai por inatividade -------------------------------------------


def test_refresh_estende_a_sessao(client: TestClient):
    """Enquanto a pessoa usa o painel, ele renova o token e a janela recomeça."""
    response = client.post("/auth/refresh")

    assert response.status_code == 200
    body = response.json()
    novo = decode_access_token(body["access_token"])
    assert novo.subject == "1"
    # a nova expiração é a janela de inatividade contada de agora
    restante = datetime.fromisoformat(body["expires_at"]) - datetime.now(UTC)
    assert timedelta(minutes=9) < restante <= timedelta(minutes=10)


def test_refresh_nao_estica_o_teto_da_sessao(client: TestClient):
    """Renovar não pode virar sessão eterna: o teto vem do token, não do relógio."""
    primeiro = decode_access_token(
        client.post("/auth/refresh").json()["access_token"]
    )
    segundo = decode_access_token(
        client.post("/auth/refresh").json()["access_token"]
    )

    assert segundo.limite == primeiro.limite


def test_refresh_sem_token_e_recusado(anon_client: TestClient):
    assert anon_client.post("/auth/refresh").status_code == 401


def test_sessao_parada_alem_da_janela_nao_renova(client: TestClient, monkeypatch):
    """Quem parou de mexer não tem o que renovar — o token já morreu no servidor."""
    from app.config import get_settings
    from app.core.security import create_access_token

    monkeypatch.setattr(get_settings(), "auth_idle_timeout_minutes", -1)
    vencido, _ = create_access_token("1")

    response = client.post(
        "/auth/refresh", headers={"Authorization": f"Bearer {vencido}"}
    )

    assert response.status_code == 401
    assert "inatividade" in response.json()["detail"]


def test_token_alem_do_teto_e_recusado(monkeypatch):
    """Passado o teto, nem um `exp` no futuro salva o token."""
    from app.core.security import create_access_token

    limite = datetime.now(UTC) - timedelta(seconds=1)
    token, _ = create_access_token("1", limite=limite)

    with pytest.raises(AuthError, match="expirada"):
        decode_access_token(token)


def test_conta_desativada_nao_renova(client: TestClient, db_session, user: User):
    """Desativar o cliente derruba a renovação na hora, sem esperar o token vencer."""
    user.is_active = False
    db_session.commit()

    assert client.post("/auth/refresh").status_code == 401
