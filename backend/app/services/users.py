"""Contas de usuário.

Não há cadastro aberto: as contas nascem pela CLI
(``python -m app.cli create-user``) e você entrega usuário e senha ao cliente.
É a superfície mais estreita possível — nada de e-mail, SMTP ou confirmação — e
abrir o cadastro depois não muda nada aqui.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.logging import get_logger
from app.core.security import AuthError, hash_password, verify_password
from app.models.user import User

logger = get_logger(__name__)


class UsernameTaken(RuntimeError):
    """Já existe uma conta com esse usuário."""


def create_user(
    session: Session,
    *,
    username: str,
    password: str,
    name: str | None = None,
) -> User:
    """Cria a conta. A senha nunca é guardada — só o hash.

    Raises:
        UsernameTaken: o usuário já existe.
    """
    username = _normalize(username)

    if get_by_username(session, username) is not None:
        raise UsernameTaken(f"Já existe uma conta com o usuário {username!r}.")

    user = User(
        username=username,
        password_hash=hash_password(password),
        name=name or None,
    )
    session.add(user)
    session.flush()

    logger.info("users.created", extra={"user_id": user.id, "username": username})
    return user


def set_password(session: Session, user: User, password: str) -> User:
    user.password_hash = hash_password(password)
    session.flush()
    logger.info("users.password_changed", extra={"user_id": user.id})
    return user


def get(session: Session, user_id: int) -> User | None:
    stmt = select(User).options(selectinload(User.bankrolls)).where(User.id == user_id)
    return session.scalars(stmt).one_or_none()


def get_by_username(session: Session, username: str) -> User | None:
    """Busca sem diferenciar maiúsculas — ninguém lembra como digitou no cadastro."""
    stmt = (
        select(User)
        .options(selectinload(User.bankrolls))
        .where(func.lower(User.username) == _normalize(username))
    )
    return session.scalars(stmt).one_or_none()


def list_users(session: Session) -> list[User]:
    stmt = select(User).options(selectinload(User.bankrolls)).order_by(User.id)
    return list(session.scalars(stmt))


def authenticate(session: Session, username: str, password: str) -> User:
    """Confere usuário e senha e devolve a conta.

    A senha é verificada mesmo quando o usuário não existe, contra um hash
    descartável: sair antes entregaria, pelo tempo de resposta, quais usuários
    existem.

    Raises:
        AuthError: usuário inexistente, senha errada ou conta desativada.
    """
    user = get_by_username(session, username)

    stored = user.password_hash if user is not None else _DUMMY_HASH
    senha_ok = verify_password(password, stored)

    if user is None or not senha_ok:
        raise AuthError("Usuário ou senha inválidos.")
    if not user.is_active:
        raise AuthError("Esta conta está desativada.")

    user.last_login_at = datetime.now(UTC)
    session.flush()
    return user


def ensure_superuser(session: Session, *, username: str, password: str) -> User | None:
    """Garante que existe uma conta administradora com este usuário.

    Chamado no start da API quando ``SUPERUSER_USERNAME``/``SUPERUSER_PASSWORD``
    estão no ambiente. É o jeito de criar o primeiro administrador num host sem
    shell — depois disso as contas nascem pelo painel.

    **Não troca a senha de quem já existe**: só promove. Assim deixar a variável
    no ambiente não desfaz uma troca de senha feita depois.

    Devolve a conta quando cria ou promove, e ``None`` quando não havia nada a
    fazer.
    """
    existente = get_by_username(session, username)

    if existente is None:
        user = create_user(session, username=username, password=password)
        user.is_superuser = True
        session.flush()
        logger.info("users.superuser_created", extra={"username": user.username})
        return user

    if not existente.is_superuser:
        existente.is_superuser = True
        session.flush()
        logger.info("users.superuser_promoted", extra={"username": existente.username})
        return existente

    return None


def _normalize(username: str) -> str:
    return username.strip().lower()


#: Hash de uma senha que ninguém tem, para o caminho do usuário inexistente
#: custar o mesmo tempo do caminho normal. Gerado uma vez por processo.
_DUMMY_HASH = hash_password("usuario-inexistente")
