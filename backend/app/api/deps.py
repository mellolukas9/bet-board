"""Dependências compartilhadas das rotas: quem está logado e o que é dele."""

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import AuthError, decode_access_token
from app.db.session import get_db
from app.models.user import Bankroll, User
from app.services import bankrolls as bankrolls_service
from app.services import users as users_service

# auto_error=False para que a falta do header vire o nosso 401 (com
# WWW-Authenticate), e não o 403 genérico do HTTPBearer.
_bearer = HTTPBearer(auto_error=False, description="Token devolvido por POST /auth/login")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    """Exige um token válido e devolve a conta dona dele.

    O ``sub`` do token é o id do usuário, e a conta é relida do banco a cada
    requisição: assim desativar um cliente tem efeito na hora, sem esperar o
    token dele expirar.
    """
    if credentials is None:
        raise _unauthorized("Autenticação obrigatória.")

    try:
        subject = decode_access_token(credentials.credentials)
    except AuthError as exc:
        raise _unauthorized(str(exc)) from exc

    user = users_service.get(session, int(subject)) if subject.isdigit() else None
    if user is None:
        raise _unauthorized("Sessão inválida. Entre de novo.")
    if not user.is_active:
        raise _unauthorized("Esta conta está desativada.")

    return user


#: Anotação pronta para injetar o usuário logado numa rota.
CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_superuser(user: CurrentUser) -> User:
    """Exige que a conta logada administre o **sistema**, não só uma banca.

    Responde 404, e não 403: as rotas de administração não existem para quem
    não é administrador — um 403 confirmaria que existe um painel a mais.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Não encontrado.",
        )
    return user


#: Anotação pronta para as rotas de /admin.
CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]


def get_owned_bankroll(
    bankroll_id: Annotated[int, Path()],
    user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Bankroll:
    """A banca da URL, desde que ela seja do usuário logado.

    Banca de outra conta responde **404**, não 403: dizer "existe, mas não é
    sua" já entrega que ela existe.
    """
    bankroll = bankrolls_service.get(session, bankroll_id)
    if bankroll is None or bankroll.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Banca {bankroll_id} não encontrada.",
        )
    return bankroll


#: Anotação pronta para as rotas aninhadas em /bankrolls/{bankroll_id}.
OwnedBankroll = Annotated[Bankroll, Depends(get_owned_bankroll)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
