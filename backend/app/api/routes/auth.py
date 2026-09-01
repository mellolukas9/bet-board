"""Login e renovação da sessão.

Não há cadastro aberto: as contas nascem pela CLI
(``python -m app.cli create-user``). O painel troca usuário+senha por um JWT e
manda esse token no ``Authorization: Bearer`` das demais rotas.

A sessão cai sozinha por inatividade (ver ``app.core.security``): o token vale
poucos minutos e o painel o renova pelo ``/auth/refresh`` enquanto a pessoa usa
a tela. Quem larga o painel aberto não renova nada, e o token expira no
servidor — não é o navegador que decide isso.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.logging import get_logger
from app.core.security import AuthError, create_access_token, decode_access_token
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import MeRead, UserRead, bankroll_to_read
from app.services import users as users_service

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

#: O mesmo esquema do `deps`, repetido aqui porque a renovação precisa do token
#: **cru** (para ler o teto da sessão), não da conta que ele representa.
_bearer = HTTPBearer(auto_error=False, description="Token devolvido por POST /auth/login")


@router.post("/login", response_model=TokenResponse, summary="Troca usuário+senha por um token")
def login(data: LoginRequest, session: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    try:
        user = users_service.authenticate(session, data.username, data.password)
    except AuthError as exc:
        logger.info("auth.login_failed", extra={"username": data.username})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    token, expires_at = create_access_token(str(user.id))
    session.commit()
    logger.info("auth.login", extra={"user_id": user.id, "username": user.username})

    return TokenResponse(access_token=token, expires_at=expires_at, username=user.username)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Estende a sessão de quem está usando o painel",
)
def refresh(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Devolve um token novo, com a janela de inatividade contada de agora.

    Quem chama é o painel, enquanto a pessoa mexe na tela. Não há segredo novo
    aqui: renovar exige um token que **ainda** vale, então uma sessão já caída
    não volta — e o teto absoluto é carregado do token antigo, não recalculado,
    para renovar não virar sessão eterna.

    A conta é relida do banco: desativar um cliente derruba a renovação dele na
    hora, sem esperar o token expirar.
    """
    if credentials is None:
        raise _nao_autorizado("Autenticação obrigatória.")

    try:
        sessao = decode_access_token(credentials.credentials)
    except AuthError as exc:
        raise _nao_autorizado(str(exc)) from exc

    user = (
        users_service.get(session, int(sessao.subject))
        if sessao.subject.isdigit()
        else None
    )
    if user is None or not user.is_active:
        raise _nao_autorizado("Sessão inválida. Entre de novo.")

    token, expires_at = create_access_token(str(user.id), limite=sessao.limite)
    return TokenResponse(access_token=token, expires_at=expires_at, username=user.username)


@router.get("/me", response_model=MeRead, summary="Quem está logado e quais bancas administra")
def me(user: CurrentUser) -> MeRead:
    """O painel chama isto ao abrir: valida o token e já traz as bancas."""
    return MeRead(
        user=UserRead.model_validate(user),
        bankrolls=[bankroll_to_read(b) for b in user.bankrolls],
    )


def _nao_autorizado(detalhe: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalhe,
        headers={"WWW-Authenticate": "Bearer"},
    )
