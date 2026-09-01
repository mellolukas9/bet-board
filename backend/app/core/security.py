"""Senha e token da sessão.

A senha é comparada contra um hash PBKDF2 (``hashlib``, sem dependência nova) e
a sessão é um JWT HS256 assinado com ``AUTH_SECRET_KEY``, com o **id do usuário**
no ``sub``.

A sessão tem **dois prazos**, e o token carrega os dois:

* ``exp`` — a inatividade. Vale poucos minutos e é renovado enquanto a pessoa
  usa o painel. Parou de mexer, ninguém renova, e o token morre no servidor.
* ``abs`` — o teto. Por mais ativa que a pessoa esteja, passado ele a senha é
  pedida de novo. Sem esse limite, uma aba aberta renovaria a sessão para
  sempre.

Quem é o usuário e se ele existe é assunto de ``app.services.users`` — aqui só
mora a criptografia.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import jwt

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

#: Formato do hash: ``pbkdf2_sha256$<iterações>$<salt b64>$<derivado b64>``.
_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 480_000
_JWT_ALGORITHM = "HS256"

#: Segredo de emergência: quando ``AUTH_SECRET_KEY`` está vazia, assina com uma
#: chave aleatória deste processo. Reiniciar a API derruba as sessões — de
#: propósito, para que a falta de configuração apareça em vez de virar um
#: segredo fixo e previsível.
_EPHEMERAL_SECRET = secrets.token_urlsafe(48)


class AuthError(RuntimeError):
    """Credencial inválida, conta desativada ou token expirado."""


class Sessao(NamedTuple):
    """O que um token válido diz."""

    #: id do usuário, como string (o ``sub`` do JWT)
    subject: str
    #: até quando esta sessão pode ser renovada, por mais ativa que a pessoa esteja
    limite: datetime


def hash_password(password: str, *, iterations: int = _ITERATIONS) -> str:
    """Gera o hash da senha, a guardar em ``user.password_hash``."""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_ALGORITHM}${iterations}${_b64(salt)}${_b64(derived)}"


def verify_password(password: str, stored: str) -> bool:
    """Confere a senha contra o hash, em tempo constante."""
    try:
        algorithm, iterations, salt_b64, derived_b64 = stored.split("$")
        if algorithm != _ALGORITHM:
            return False
        salt = _unb64(salt_b64)
        expected = _unb64(derived_b64)
    except (ValueError, TypeError):
        # hash malformado no banco — trata como senha errada, não como crash
        logger.warning("auth.password_hash_malformed")
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    return hmac.compare_digest(candidate, expected)


def create_access_token(
    subject: str, *, limite: datetime | None = None
) -> tuple[str, datetime]:
    """Assina o JWT da sessão para o ``subject`` (o id do usuário, como string).

    O ``exp`` é a janela de inatividade; ``limite`` é o teto absoluto da sessão,
    que a renovação **carrega adiante** em vez de recalcular — é o que impede
    que renovar para sempre valha por não expirar nunca. Sem ele (é o caso do
    login), o teto nasce agora.

    Devolve ``(token, expiração)``. A expiração nunca passa do teto: perto do
    fim, a última renovação vale menos que a janela cheia.
    """
    settings = get_settings()
    agora = datetime.now(UTC)

    if limite is None:
        limite = agora + timedelta(minutes=settings.auth_token_ttl_minutes)

    expires_at = min(agora + timedelta(minutes=settings.auth_idle_timeout_minutes), limite)

    token = jwt.encode(
        {
            "sub": subject,
            "iat": agora,
            "exp": expires_at,
            "abs": int(limite.timestamp()),
        },
        _secret(),
        algorithm=_JWT_ALGORITHM,
    )
    return token, expires_at


def decode_access_token(token: str) -> Sessao:
    """Devolve o ``sub`` e o teto da sessão.

    Raises:
        AuthError: token inválido, adulterado ou expirado (por inatividade ou
            por ter passado do teto).
    """
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Sessão expirada por inatividade. Entre de novo.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Token inválido.") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthError("Token inválido.")

    limite = _limite_de(payload)
    if limite <= datetime.now(UTC):
        raise AuthError("Sessão expirada. Entre de novo.")

    return Sessao(subject=subject, limite=limite)


def _limite_de(payload: dict) -> datetime:
    """O teto gravado no token.

    Token emitido antes de o teto existir não tem o campo; nesse caso ele vale
    o próprio ``exp``, e a sessão simplesmente não é renovável. Ninguém é
    deslogado no meio de um deploy por causa de um campo novo.
    """
    bruto = payload.get("abs")
    if not isinstance(bruto, (int, float)):
        bruto = payload["exp"]
    return datetime.fromtimestamp(bruto, UTC)


def _secret() -> str:
    settings = get_settings()
    if settings.auth_secret_key:
        return settings.auth_secret_key

    logger.warning("auth.secret_key_missing")
    return _EPHEMERAL_SECRET


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
