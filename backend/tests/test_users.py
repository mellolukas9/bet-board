"""Contas de usuário — criadas pela CLI, nunca por cadastro aberto."""

import pytest

from app.core.security import verify_password
from app.services import bankrolls as bankrolls_service
from app.services import users as users_service
from tests.conftest import TEST_ITERATIONS


def test_cria_conta_guardando_só_o_hash(db_session):
    user = users_service.create_user(
        db_session, username="Pecanha", password="uma-senha", name="Peçanha"
    )
    db_session.commit()

    assert user.username == "pecanha"  # normalizado para minúsculas
    assert user.name == "Peçanha"
    assert "uma-senha" not in user.password_hash
    assert verify_password("uma-senha", user.password_hash)


def test_usuario_repetido_e_recusado(db_session):
    users_service.create_user(db_session, username="pecanha", password="x")
    db_session.commit()

    with pytest.raises(users_service.UsernameTaken):
        users_service.create_user(db_session, username="PECANHA", password="y")


def test_troca_de_senha(db_session, user):
    users_service.set_password(db_session, user, "nova-senha")
    db_session.commit()

    assert verify_password("nova-senha", user.password_hash)
    assert not verify_password("senha-de-teste", user.password_hash)


def test_lista_contas_com_as_bancas(db_session):
    user = users_service.create_user(db_session, username="pecanha", password="x")
    bankrolls_service.create_bankroll(db_session, user, name="Vip")
    bankrolls_service.create_bankroll(db_session, user, name="Free")
    db_session.commit()

    contas = users_service.list_users(db_session)

    assert len(contas) == 1
    assert [b.slug for b in contas[0].bankrolls] == ["vip", "free"]


def test_apagar_conta_leva_bancas_e_tips(db_session, user, bankroll):
    """Cancelar um cliente não pode deixar banca órfã no banco."""
    from app.models.tip import Tip
    from app.models.user import Bankroll

    db_session.add(Tip(bankroll_id=bankroll.id, event="Time A x Time B", currency="BRL"))
    db_session.commit()

    db_session.delete(user)
    db_session.commit()

    assert db_session.query(Bankroll).count() == 0
    assert db_session.query(Tip).count() == 0


def test_conta_nova_nasce_ativa(db_session):
    user = users_service.create_user(db_session, username="pecanha", password="x")

    assert user.is_active


def test_hash_de_teste_e_o_de_producao_sao_o_mesmo_formato(db_session):
    """A suíte baixa as iterações; o formato do hash não muda por isso."""
    from app.core.security import hash_password

    barato = hash_password("x", iterations=TEST_ITERATIONS)

    assert barato.startswith("pbkdf2_sha256$")
    assert verify_password("x", barato)
