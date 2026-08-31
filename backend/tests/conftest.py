import os

os.environ.setdefault("ENVIRONMENT", "test")
# Chave de assinatura fixada antes de importar a app: o Settings é lru_cache,
# então quem lê primeiro define o valor do processo inteiro.
os.environ.setdefault("AUTH_SECRET_KEY", "segredo-de-teste-com-mais-de-32-bytes-para-o-hs256")
# O bootstrap do primeiro administrador não pode rodar na suíte: ele criaria uma
# conta a mais em todo teste que sobe a app.
os.environ.setdefault("SUPERUSER_USERNAME", "")
os.environ.setdefault("SUPERUSER_PASSWORD", "")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import tip as _tip_models  # noqa: E402,F401  (registra as tabelas)
from app.models import user as _user_models  # noqa: E402,F401
from app.models.user import Bankroll, User  # noqa: E402
from app.services import bankrolls as bankrolls_service  # noqa: E402

USERNAME = "tipster"
PASSWORD = "senha-de-teste"
ADMIN_CREDENTIALS = {"username": USERNAME, "password": PASSWORD}

# O PBKDF2 de produção usa 480 mil iterações (~0,3s). Numa suíte que cria um
# usuário por teste isso viraria minutos de espera — e o número de iterações
# está gravado no próprio hash, então baixá-lo aqui não muda o código testado.
TEST_ITERATIONS = 1_000


@pytest.fixture
def db_session():
    """Banco de verdade, em SQLite na memória — um por teste, descartado no fim.

    Roda o mesmo model do Postgres (o ``result_raw`` JSONB tem variante SQLite),
    então a suíte não precisa de Docker de pé para exercitar as rotas.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        # StaticPool: a conexão é a mesma em todo o teste, senão o ":memory:"
        # some entre um checkout e outro do pool.
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    session: Session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def user(db_session) -> User:
    """A conta usada pelos testes autenticados."""
    user = User(
        username=USERNAME,
        password_hash=hash_password(PASSWORD, iterations=TEST_ITERATIONS),
        name="Tipster de Teste",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def bankroll(db_session, user: User) -> Bankroll:
    """A banca padrão dos testes: é dela que as tips são."""
    bankroll = bankrolls_service.create_bankroll(db_session, user, name="Banca de Teste")
    db_session.commit()
    return bankroll


@pytest.fixture
def outro_usuario(db_session) -> User:
    """Uma segunda conta, para provar que uma não enxerga a outra."""
    outro = User(
        username="intruso",
        password_hash=hash_password("outra-senha", iterations=TEST_ITERATIONS),
    )
    db_session.add(outro)
    db_session.commit()
    return outro


@pytest.fixture
def anon_client(db_session) -> TestClient:
    """Cliente HTTP **sem** login, com o ``get_db`` no banco do teste."""

    def override():
        # Em produção cada request abre a sua sessão e enxerga o banco como ele
        # está. Aqui a sessão é uma só (para o teste e a rota compartilharem o
        # SQLite em memória), então expirar antes de cada request recria esse
        # comportamento — sem isso, uma coleção já carregada continuaria
        # devolvendo o que era verdade no primeiro acesso.
        db_session.expire_all()
        yield db_session

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(anon_client: TestClient, user: User) -> TestClient:
    """Cliente já logado.

    Passa pelo ``POST /auth/login`` de verdade em vez de sobrescrever a
    dependência: assim toda a suíte exercita o caminho autenticado real.
    """
    response = anon_client.post("/auth/login", json=ADMIN_CREDENTIALS)
    assert response.status_code == 200, response.text
    anon_client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return anon_client


def login_as(client: TestClient, user: User, password: str) -> TestClient:
    """Troca a sessão do cliente para outra conta."""
    response = client.post(
        "/auth/login", json={"username": user.username, "password": password}
    )
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return client
