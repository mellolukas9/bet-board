"""Painel de administração do sistema — as contas dos clientes."""

import pytest
from fastapi.testclient import TestClient

from app.core.security import verify_password
from app.models.user import User
from app.services import bankrolls as bankrolls_service
from app.services import users as users_service
from tests.conftest import PASSWORD, TEST_ITERATIONS, login_as


@pytest.fixture
def admin(db_session, user: User) -> User:
    """A conta de teste promovida a administradora do sistema."""
    user.is_superuser = True
    db_session.commit()
    return user


def test_cliente_comum_nao_enxerga_a_administracao(client: TestClient) -> None:
    """404, não 403: um 403 já contaria que existe um painel a mais."""
    assert client.get("/admin/users").status_code == 404
    criar = client.post("/admin/users", json={"username": "x", "password": "12345678"})
    assert criar.status_code == 404


def test_administracao_exige_login(anon_client: TestClient) -> None:
    assert anon_client.get("/admin/users").status_code == 401


def test_lista_as_contas_com_as_contagens(
    client: TestClient, admin: User, bankroll, db_session
) -> None:
    from app.models.tip import Tip

    db_session.add(Tip(bankroll_id=bankroll.id, event="Time A x Time B", currency="BRL"))
    db_session.commit()

    contas = client.get("/admin/users").json()

    assert len(contas) == 1
    assert contas[0]["username"] == admin.username
    assert contas[0]["is_superuser"] is True
    assert contas[0]["bankrolls"] == 1
    assert contas[0]["tips"] == 1


def test_conta_sem_banca_conta_zero(client: TestClient, admin: User) -> None:
    conta = client.get("/admin/users").json()[0]

    assert conta["bankrolls"] == 0
    assert conta["tips"] == 0


def test_cria_conta_de_cliente(client: TestClient, admin: User) -> None:
    response = client.post(
        "/admin/users",
        json={
            "username": "pecanha",
            "password": "senha-do-cliente",
            "name": "Peçanha",
            "bankroll_name": "Vip Peçanha",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "pecanha"
    assert body["is_superuser"] is False
    assert body["bankrolls"] == 1


def test_conta_criada_ja_entra_no_painel(
    client: TestClient, admin: User, anon_client: TestClient
) -> None:
    client.post(
        "/admin/users",
        json={"username": "pecanha", "password": "senha-do-cliente"},
    )

    entrada = anon_client.post(
        "/auth/login", json={"username": "pecanha", "password": "senha-do-cliente"}
    )

    assert entrada.status_code == 200


def test_usuario_repetido_e_409(client: TestClient, admin: User) -> None:
    client.post("/admin/users", json={"username": "pecanha", "password": "senha-boa-1"})

    response = client.post(
        "/admin/users", json={"username": "pecanha", "password": "senha-boa-2"}
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "corpo",
    [
        {"username": "ab", "password": "senha-boa-1"},  # usuário curto demais
        {"username": "pecanha", "password": "curta"},  # senha curta demais
        {"username": "com espaço", "password": "senha-boa-1"},
    ],
)
def test_dados_invalidos_sao_recusados(client: TestClient, admin: User, corpo: dict) -> None:
    assert client.post("/admin/users", json=corpo).status_code == 422


def test_desativa_uma_conta(client: TestClient, admin: User, db_session) -> None:
    criada = client.post(
        "/admin/users", json={"username": "pecanha", "password": "senha-do-cliente"}
    ).json()

    body = client.patch(f"/admin/users/{criada['id']}", json={"is_active": False}).json()

    assert body["is_active"] is False


def test_conta_desativada_para_de_entrar(
    client: TestClient, admin: User, anon_client: TestClient
) -> None:
    criada = client.post(
        "/admin/users", json={"username": "pecanha", "password": "senha-do-cliente"}
    ).json()
    client.patch(f"/admin/users/{criada['id']}", json={"is_active": False})

    entrada = anon_client.post(
        "/auth/login", json={"username": "pecanha", "password": "senha-do-cliente"}
    )

    assert entrada.status_code == 401
    assert "desativada" in entrada.json()["detail"]


def test_troca_a_senha_de_um_cliente(client: TestClient, admin: User, db_session) -> None:
    """É o caminho de "o cliente perdeu a senha"."""
    criada = client.post(
        "/admin/users", json={"username": "pecanha", "password": "senha-antiga-1"}
    ).json()

    client.patch(f"/admin/users/{criada['id']}", json={"password": "senha-nova-123"})

    cliente = users_service.get(db_session, criada["id"])
    assert verify_password("senha-nova-123", cliente.password_hash)


def test_promove_outra_conta(client: TestClient, admin: User) -> None:
    criada = client.post(
        "/admin/users", json={"username": "socio", "password": "senha-do-socio"}
    ).json()

    body = client.patch(f"/admin/users/{criada['id']}", json={"is_superuser": True}).json()

    assert body["is_superuser"] is True


def test_nao_se_desativa(client: TestClient, admin: User) -> None:
    """Sem isto, um clique tranca você para fora e só o banco resolve."""
    response = client.patch(f"/admin/users/{admin.id}", json={"is_active": False})

    assert response.status_code == 409
    assert "própria conta" in response.json()["detail"]


def test_nao_se_rebaixa(client: TestClient, admin: User) -> None:
    response = client.patch(f"/admin/users/{admin.id}", json={"is_superuser": False})

    assert response.status_code == 409


def test_nao_se_apaga(client: TestClient, admin: User) -> None:
    assert client.delete(f"/admin/users/{admin.id}").status_code == 409


def test_apaga_conta_sem_banca(client: TestClient, admin: User) -> None:
    criada = client.post(
        "/admin/users", json={"username": "engano", "password": "senha-qualquer"}
    ).json()

    assert client.delete(f"/admin/users/{criada['id']}").status_code == 204
    assert len(client.get("/admin/users").json()) == 1


def test_recusa_apagar_conta_com_banca(client: TestClient, admin: User) -> None:
    """Desativar é quase sempre o que se quer; apagar leva o histórico junto."""
    criada = client.post(
        "/admin/users",
        json={"username": "pecanha", "password": "senha-boa-1", "bankroll_name": "Vip"},
    ).json()

    response = client.delete(f"/admin/users/{criada['id']}")

    assert response.status_code == 409
    assert "Desative" in response.json()["detail"]


def test_conta_inexistente_e_404(client: TestClient, admin: User) -> None:
    assert client.patch("/admin/users/999", json={"is_active": False}).status_code == 404
    assert client.delete("/admin/users/999").status_code == 404


def test_admin_nao_enxerga_as_bancas_dos_clientes(
    client: TestClient, admin: User, db_session
) -> None:
    """Administrar contas não é o mesmo que entrar na banca de alguém."""
    cliente = users_service.create_user(db_session, username="pecanha", password="x")
    alheia = bankrolls_service.create_bankroll(db_session, cliente, name="Vip")
    db_session.commit()

    assert client.get(f"/bankrolls/{alheia.id}").status_code == 404
    assert [b["slug"] for b in client.get("/bankrolls").json()] == []


# --- primeiro administrador em deploy remoto ----------------------------------


def test_bootstrap_cria_o_primeiro_administrador(db_session) -> None:
    criado = users_service.ensure_superuser(
        db_session, username="lucas", password="senha-inicial"
    )
    db_session.commit()

    assert criado is not None
    assert criado.is_superuser
    assert criado.username == "lucas"


def test_bootstrap_promove_conta_existente(db_session, user: User) -> None:
    promovido = users_service.ensure_superuser(
        db_session, username=user.username, password="ignorada"
    )
    db_session.commit()

    assert promovido is not None
    assert user.is_superuser


def test_bootstrap_nao_troca_a_senha_de_quem_ja_existe(db_session, admin: User) -> None:
    """A variável fica no ambiente do host; ela não pode desfazer uma troca."""
    users_service.set_password(db_session, admin, "senha-trocada-depois")
    db_session.commit()

    resultado = users_service.ensure_superuser(
        db_session, username=admin.username, password="senha-do-ambiente"
    )
    db_session.commit()

    assert resultado is None
    assert verify_password("senha-trocada-depois", admin.password_hash)


def test_bootstrap_rodado_duas_vezes_nao_duplica(db_session) -> None:
    users_service.ensure_superuser(db_session, username="lucas", password="x")
    db_session.commit()
    users_service.ensure_superuser(db_session, username="lucas", password="x")
    db_session.commit()

    assert len(users_service.list_users(db_session)) == 1


def test_cliente_promovido_passa_a_enxergar_a_administracao(
    client: TestClient, user: User, outro_usuario: User, db_session
) -> None:
    """O papel é lido do banco a cada requisição, não do token."""
    login_as(client, user, PASSWORD)
    assert client.get("/admin/users").status_code == 404

    user.is_superuser = True
    db_session.commit()

    assert client.get("/admin/users").status_code == 200


def test_hash_do_teste_continua_barato(db_session) -> None:
    """Guarda-chuva: se alguém subir as iterações do fixture, a suíte trava."""
    assert TEST_ITERATIONS <= 10_000
