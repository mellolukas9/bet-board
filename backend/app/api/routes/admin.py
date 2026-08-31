"""Administração do sistema — as contas dos clientes.

Painel separado do painel do tipster, e de propósito: o cliente administra a
banca dele, você administra quem tem conta. Só uma conta com ``is_superuser``
enxerga estas rotas.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentSuperuser
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.tip import Tip
from app.models.user import Bankroll, User
from app.schemas.user import AdminUserCreate, AdminUserRead, AdminUserUpdate
from app.services import bankrolls as bankrolls_service
from app.services import users as users_service

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserRead], summary="Todas as contas")
def list_users(
    admin: CurrentSuperuser,  # noqa: ARG001
    session: Annotated[Session, Depends(get_db)],
) -> list[AdminUserRead]:
    """Contas com quantas bancas e tips cada uma tem.

    As contagens vêm em duas consultas agregadas, não uma por conta: com 50
    clientes a versão ingênua seriam 101 idas ao banco para desenhar uma lista.
    """
    contas = users_service.list_users(session)
    bancas_por_conta = _contar_bancas(session)
    tips_por_conta = _contar_tips(session)

    return [
        AdminUserRead(
            id=u.id,
            username=u.username,
            name=u.name,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
            bankrolls=bancas_por_conta.get(u.id, 0),
            tips=tips_por_conta.get(u.id, 0),
        )
        for u in contas
    ]


@router.post(
    "/users",
    response_model=AdminUserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cria a conta de um cliente",
)
def create_user(
    data: AdminUserCreate,
    admin: CurrentSuperuser,
    session: Annotated[Session, Depends(get_db)],
) -> AdminUserRead:
    """A senha é definida por você e entregue ao cliente.

    Não há e-mail nem confirmação: enquanto você conhece cada cliente, isso é
    uma tela a menos e uma superfície de abuso a menos.
    """
    try:
        user = users_service.create_user(
            session, username=data.username, password=data.password, name=data.name
        )
    except users_service.UsernameTaken as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    user.is_superuser = data.is_superuser

    bancas = 0
    if data.bankroll_name:
        bankrolls_service.create_bankroll(session, user, name=data.bankroll_name)
        bancas = 1

    session.commit()
    logger.info(
        "admin.user_created",
        extra={"by": admin.username, "user_id": user.id, "username": user.username},
    )

    return AdminUserRead(
        id=user.id,
        username=user.username,
        name=user.name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        bankrolls=bancas,
        tips=0,
    )


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserRead,
    summary="Ativa, desativa, promove ou troca a senha de uma conta",
)
def update_user(
    user_id: int,
    data: AdminUserUpdate,
    admin: CurrentSuperuser,
    session: Annotated[Session, Depends(get_db)],
) -> AdminUserRead:
    user = _get_or_404(session, user_id)
    changes = data.model_dump(exclude_unset=True)

    # Desativar ou rebaixar a si mesmo tranca você para fora do próprio painel,
    # e não há outro caminho de volta além do banco.
    if user.id == admin.id:
        if changes.get("is_active") is False:
            raise _recusado("Você não pode desativar a própria conta.")
        if changes.get("is_superuser") is False:
            raise _recusado("Você não pode remover o próprio acesso de administrador.")

    if (senha := changes.pop("password", None)) is not None:
        users_service.set_password(session, user, senha)

    for campo, valor in changes.items():
        setattr(user, campo, valor)

    session.commit()
    logger.info(
        "admin.user_updated",
        extra={
            "by": admin.username,
            "user_id": user.id,
            "fields": sorted(data.model_dump(exclude_unset=True)),
        },
    )
    return _com_contagens(session, user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Apaga uma conta e tudo que é dela",
)
def delete_user(
    user_id: int,
    admin: CurrentSuperuser,
    session: Annotated[Session, Depends(get_db)],
) -> None:
    """Leva junto as bancas e as tips, por cascade.

    Recusa contas que ainda têm banca: **desativar** é quase sempre o que se
    quer (o cliente para de entrar, o histórico fica). Apagar é para conta
    criada por engano.
    """
    user = _get_or_404(session, user_id)

    if user.id == admin.id:
        raise _recusado("Você não pode apagar a própria conta.")

    bancas = session.scalar(
        select(func.count()).select_from(Bankroll).where(Bankroll.user_id == user.id)
    )
    if bancas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Esta conta tem {bancas} banca(s). Desative-a para tirar o acesso "
                "sem perder o histórico, ou apague as bancas antes."
            ),
        )

    session.delete(user)
    session.commit()
    logger.info("admin.user_deleted", extra={"by": admin.username, "user_id": user_id})


def _get_or_404(session: Session, user_id: int) -> User:
    user = users_service.get(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Conta {user_id} não encontrada."
        )
    return user


def _com_contagens(session: Session, user: User) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        username=user.username,
        name=user.name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        bankrolls=_contar_bancas(session).get(user.id, 0),
        tips=_contar_tips(session).get(user.id, 0),
    )


def _contar_bancas(session: Session) -> dict[int, int]:
    linhas = session.execute(
        select(Bankroll.user_id, func.count()).group_by(Bankroll.user_id)
    )
    return dict(linhas.all())


def _contar_tips(session: Session) -> dict[int, int]:
    linhas = session.execute(
        select(Bankroll.user_id, func.count(Tip.id))
        .join(Tip, Tip.bankroll_id == Bankroll.id)
        .group_by(Bankroll.user_id)
    )
    return dict(linhas.all())


def _recusado(detalhe: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detalhe)
