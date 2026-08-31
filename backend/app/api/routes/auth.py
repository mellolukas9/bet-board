"""Login.

Não há cadastro aberto: as contas nascem pela CLI
(``python -m app.cli create-user``). O painel troca usuário+senha por um JWT e
manda esse token no ``Authorization: Bearer`` das demais rotas.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.logging import get_logger
from app.core.security import AuthError, create_access_token
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import MeRead, UserRead, bankroll_to_read
from app.services import users as users_service

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.get("/me", response_model=MeRead, summary="Quem está logado e quais bancas administra")
def me(user: CurrentUser) -> MeRead:
    """O painel chama isto ao abrir: valida o token e já traz as bancas."""
    return MeRead(
        user=UserRead.model_validate(user),
        bankrolls=[bankroll_to_read(b) for b in user.bankrolls],
    )
