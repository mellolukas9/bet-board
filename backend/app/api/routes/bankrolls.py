"""Bancas: criar, configurar e conectar o canal do Telegram."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, OwnedBankroll
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.user import (
    BankrollCreate,
    BankrollRead,
    BankrollUpdate,
    ChatDetectado,
    ChatsDetectados,
    TelegramCheck,
    TelegramDiagnostico,
    bankroll_to_read,
)
from app.services import bankrolls as bankrolls_service
from app.services import telegram_setup
from app.services.bankrolls import SlugEmUso

logger = get_logger(__name__)

router = APIRouter(prefix="/bankrolls", tags=["bankrolls"])

DICA_SEM_CHATS = (
    "Nenhuma conversa apareceu ainda. Adicione o bot ao canal como "
    "administrador, mande qualquer mensagem lá e clique em detectar de novo — "
    "o Telegram só mostra os canais em que o bot já viu alguma atividade."
)


@router.get("", response_model=list[BankrollRead], summary="As bancas da conta logada")
def list_bankrolls(
    user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> list[BankrollRead]:
    return [bankroll_to_read(b) for b in bankrolls_service.list_for_user(session, user)]


@router.post(
    "",
    response_model=BankrollRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma banca",
)
def create_bankroll(
    data: BankrollCreate,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> BankrollRead:
    """O endereço público (`/b/<slug>`) é derivado do nome, sempre."""
    try:
        bankroll = bankrolls_service.create_bankroll(
            session,
            user,
            name=data.name,
            description=data.description,
            is_public=data.is_public,
        )
    except SlugEmUso as exc:
        raise _slug_recusado(exc) from exc

    session.commit()
    return bankroll_to_read(bankroll)


@router.get("/{bankroll_id}", response_model=BankrollRead, summary="Detalhe da banca")
def read_bankroll(bankroll: OwnedBankroll) -> BankrollRead:
    return bankroll_to_read(bankroll)


@router.patch(
    "/{bankroll_id}",
    response_model=BankrollRead,
    summary="Renomeia, troca o endereço público ou configura os canais",
)
def patch_bankroll(
    data: BankrollUpdate,
    bankroll: OwnedBankroll,
    session: Annotated[Session, Depends(get_db)],
) -> BankrollRead:
    """Renomear muda o endereço público junto: `/b/<slug>` segue o nome.

    Campo de canal enviado vazio (``""``) **apaga** o valor — é como se
    desconecta o Telegram.
    """
    changes = data.model_dump(exclude_unset=True)

    for campo in ("telegram_bot_token", "telegram_chat_id", "whatsapp_webhook_url"):
        if campo in changes and changes[campo] is not None:
            changes[campo] = changes[campo].strip() or None

    try:
        bankrolls_service.update_bankroll(session, bankroll, changes)
    except SlugEmUso as exc:
        raise _slug_recusado(exc) from exc

    session.commit()
    return bankroll_to_read(bankroll)


@router.delete(
    "/{bankroll_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Apaga a banca e todas as tips dela",
)
def delete_bankroll(
    bankroll: OwnedBankroll,
    session: Annotated[Session, Depends(get_db)],
) -> None:
    """Recusa enquanto houver tip: apagar histórico não pode ser um clique só."""
    total = bankrolls_service.count_tips(session, bankroll)
    if total:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Esta banca tem {total} tip(s). Apague as tips antes, ou "
                "mantenha a banca como histórico."
            ),
        )

    bankrolls_service.delete_bankroll(session, bankroll)
    session.commit()


# --- assistente do Telegram ---------------------------------------------------


@router.post(
    "/{bankroll_id}/telegram/test",
    response_model=TelegramDiagnostico,
    summary="Confere token, canal e permissão de publicar",
)
def test_telegram(
    data: TelegramCheck,
    bankroll: OwnedBankroll,
) -> TelegramDiagnostico:
    """Testa o que o cliente acabou de digitar, mesmo antes de salvar.

    Sem valores no corpo, testa o que já está salvo na banca — é o botão
    "testar de novo" depois de mexer no canal pelo aplicativo.
    """
    token = data.bot_token or bankroll.telegram_bot_token
    chat_id = data.chat_id or bankroll.telegram_chat_id

    try:
        resultado = telegram_setup.diagnose(token, chat_id)
    except telegram_setup.TelegramSetupError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    logger.info(
        "telegram.diagnosed",
        extra={"bankroll_id": bankroll.id, "ok": resultado.ok},
    )
    return TelegramDiagnostico(**vars(resultado))


@router.post(
    "/{bankroll_id}/telegram/detect",
    response_model=ChatsDetectados,
    summary="Lista os canais que o bot enxerga, para descobrir o chat_id",
)
def detect_telegram_chats(
    data: TelegramCheck,
    bankroll: OwnedBankroll,
) -> ChatsDetectados:
    """Resolve a parte mais chata da configuração.

    Canal privado não tem @nome e não mostra o id em lugar nenhum do aplicativo.
    Aqui o bot lista as conversas que ele viu, e o cliente só escolhe a certa.
    """
    token = data.bot_token or bankroll.telegram_bot_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o token do bot antes de detectar os canais.",
        )

    try:
        chats = telegram_setup.detect_chats(token)
    except telegram_setup.TelegramSetupError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ChatsDetectados(
        chats=[ChatDetectado(**vars(c)) for c in chats],
        dica=None if chats else DICA_SEM_CHATS,
    )


def _slug_recusado(exc: SlugEmUso) -> HTTPException:
    """Não sobrou endereço a partir desse nome — só acontece com nome repetido
    centenas de vezes, mas 409 diz melhor que 500 o que houve."""
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
