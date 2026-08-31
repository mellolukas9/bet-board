"""Senha e token da sessão.

A senha é comparada contra um hash PBKDF2 (``hashlib``, sem dependência nova) e
a sessão é um JWT HS256 assinado com ``AUTH_SECRET_KEY``, com o **id do usuário**
no ``sub``.

Quem é o usuário e se ele existe é assunto de ``app.services.users`` — aqui só
mora a criptografia.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

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


def create_access_token(subject: str) -> tuple[str, datetime]:
    """Assina o JWT da sessão para o ``subject`` (o id do usuário, como string).

    Devolve ``(token, expiração)``.
    """
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.auth_token_ttl_minutes)

    token = jwt.encode(
        {"sub": subject, "iat": datetime.now(UTC), "exp": expires_at},
        _secret(),
        algorithm=_JWT_ALGORITHM,
    )
    return token, expires_at


def decode_access_token(token: str) -> str:
    """Devolve o ``sub`` do token.

    Raises:
        AuthError: token inválido, adulterado ou expirado.
    """
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Sessão expirada. Entre de novo.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Token inválido.") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthError("Token inválido.")
    return subject


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
