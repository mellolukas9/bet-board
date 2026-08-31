"""Rotas de tips.

Dois routers, por causa da hierarquia ``bankroll → tip``:

* **``nested_router``** (``/bankrolls/{bankroll_id}/tips``) — o que é coleção:
  criar e listar. A banca precisa estar na URL porque é ela que define de quem
  é a tip e em qual canal ela sai.
* **``router``** (``/tips/{tip_id}``) — o que é item: ler, corrigir, marcar
  resultado, publicar, descartar. O id da tip já basta; a dona sai dele, e a
  permissão é conferida contra o usuário logado.

Duas portas de entrada para a leitura do print, de propósito:

* ``POST /tips/preview`` — lê e devolve o resultado **sem gravar**. Serve para
  calibrar extração e texto.
* ``POST /bankrolls/{id}/tips`` — o fluxo de verdade: grava a tip (mesmo mal
  lida), que fica aguardando revisão. A publicação é um passo à parte, porque o
  stake em unidades é informado pelo admin no ``PATCH`` — o print só traz reais.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, OwnedBankroll
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.tip import Tip, TipStatus
from app.models.user import User
from app.schemas.tip import (
    TipExtracted,
    TipPublish,
    TipPublishResponse,
    TipRead,
    TipResult,
    TipUpdate,
)
from app.services import tips as tips_service
from app.services.messaging import channels_of, format_tip_message, get_message_senders
from app.services.tips import TipNotDiscardable, TipNotPublishable
from app.services.vision import (
    UnsupportedImageError,
    VisionError,
    detect_media_type,
    get_vision_extractor,
)

logger = get_logger(__name__)

#: Rotas de item: /tips/{tip_id}
router = APIRouter(prefix="/tips", tags=["tips"])

#: Rotas de coleção, aninhadas na banca dona das tips.
nested_router = APIRouter(prefix="/bankrolls/{bankroll_id}/tips", tags=["tips"])

# Print de casa de aposta não passa disso; o limite existe para não segurar
# um upload absurdo na memória antes de mandar para a API de visão.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class TipPreviewResponse(BaseModel):
    """Resultado da leitura de um print, sem persistência."""

    tip: TipExtracted
    message: str | None
    is_complete: bool
    missing_fields: list[str]
    needs_review: bool


def _read_upload(file: UploadFile) -> tuple[bytes, str]:
    """Valida o upload e descobre o formato real pelos magic bytes."""
    data = file.file.read()

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo vazio.",
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Imagem acima do limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        return data, detect_media_type(data, file.filename)
    except UnsupportedImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc


def _get_owned_tip(session: Session, tip_id: int, user: User) -> Tip:
    """A tip, desde que a banca dela seja do usuário logado.

    Tip de outra conta responde **404** pelo mesmo motivo da banca: um 403
    confirmaria que ela existe.
    """
    tip = tips_service.get_tip(session, tip_id)
    if tip is None or tip.bankroll.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tip {tip_id} não encontrada.",
        )
    return tip


# --- coleção: /bankrolls/{bankroll_id}/tips -----------------------------------


@nested_router.post(
    "",
    response_model=TipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Recebe um print, lê e grava a tip na banca",
)
def create_tip(
    file: Annotated[UploadFile, File()],
    bankroll: OwnedBankroll,
    session: Annotated[Session, Depends(get_db)],
) -> Tip:
    """Grava a tip lida do print, sempre em ``pending``.

    Print ilegível ou provedor fora do ar **não** perde a tip: ela é gravada
    com ``extraction_error`` para o admin completar à mão.
    """
    data, media_type = _read_upload(file)

    try:
        extractor = get_vision_extractor()
    except (VisionError, ValueError) as exc:
        # erro de configuração (chave ausente, provedor inválido) — não adianta
        # gravar tip nenhuma, é o servidor que está mal configurado
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    tip = tips_service.create_tip_from_image(
        session,
        bankroll=bankroll,
        image=data,
        media_type=media_type,
        extractor=extractor,
        raw_image_ref=file.filename,
    )
    session.commit()
    return tip


@nested_router.get(
    "",
    response_model=list[TipRead],
    summary="Lista as tips da banca, mais recentes primeiro",
)
def list_tips(
    bankroll: OwnedBankroll,
    session: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[TipStatus | None, Query(alias="status")] = None,
    needs_review: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Tip]:
    """``?needs_review=true`` é a fila de revisão manual do painel."""
    return tips_service.list_tips(
        session,
        bankroll_id=bankroll.id,
        status=status_filter,
        needs_review=needs_review,
        limit=limit,
        offset=offset,
    )


# --- item: /tips/{tip_id} -----------------------------------------------------


@router.post(
    "/preview",
    response_model=TipPreviewResponse,
    summary="Lê um print e devolve a tip + a mensagem, sem gravar",
)
def preview_tip(
    file: Annotated[UploadFile, File()],
    user: CurrentUser,  # noqa: ARG001  (só exige login; não grava nada)
) -> TipPreviewResponse:
    """Extrai a tip do print e monta a mensagem que iria para o grupo.

    Endpoint síncrono de propósito: a chamada à API de visão é bloqueante, e o
    FastAPI roda ``def`` num threadpool em vez de travar o event loop.
    """
    data, media_type = _read_upload(file)

    try:
        extractor = get_vision_extractor()
        tip = extractor.extract(data, media_type)
    except VisionError as exc:
        # falha do provedor (chave, quota, rede, recusa) — é 502, não erro do cliente
        logger.warning("tips.preview.vision_error", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    # Print ilegível não gera mensagem — vai para revisão manual.
    message = format_tip_message(tip) if tip.unreadable_reason is None else None

    logger.info(
        "tips.preview",
        extra={
            # "filename" é reservado pelo LogRecord do stdlib — não usar aqui
            "upload_name": file.filename,
            "complete": tip.is_complete,
            "missing_fields": tip.missing_fields,
        },
    )

    return TipPreviewResponse(
        tip=tip,
        message=message,
        is_complete=tip.is_complete,
        missing_fields=tip.missing_fields,
        needs_review=not tip.is_complete,
    )


@router.get("/{tip_id}", response_model=TipRead, summary="Detalhe de uma tip")
def read_tip(
    tip_id: int,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Tip:
    return _get_owned_tip(session, tip_id, user)


@router.patch(
    "/{tip_id}",
    response_model=TipRead,
    summary="Corrige manualmente uma tip (inclusive o stake em unidades)",
)
def patch_tip(
    tip_id: int,
    data: TipUpdate,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Tip:
    tip = _get_owned_tip(session, tip_id, user)
    tips_service.update_tip(session, tip, data)
    session.commit()
    return tip


@router.delete(
    "/{tip_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Descarta uma tip que não vai ser publicada",
)
def delete_tip(
    tip_id: int,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> None:
    """Apaga a tip. Recusa (409) se ela já tiver ido para o grupo."""
    tip = _get_owned_tip(session, tip_id, user)

    try:
        tips_service.discard_tip(session, tip)
    except TipNotDiscardable as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    session.commit()


@router.post(
    "/{tip_id}/result",
    response_model=TipRead,
    summary="O admin marca a tip como green, red ou void",
)
def set_tip_result(
    tip_id: int,
    body: TipResult,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Tip:
    """Resultado informado à mão — não há API esportiva nesta fase.

    ``status: "pending"`` desfaz um resultado marcado por engano.
    """
    tip = _get_owned_tip(session, tip_id, user)
    tips_service.set_result(session, tip, body.status, body.note)
    session.commit()
    session.refresh(tip)
    return tip


@router.post(
    "/{tip_id}/publish",
    response_model=TipPublishResponse,
    summary="Publica a tip nos canais da banca",
)
def publish_tip(
    tip_id: int,
    user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    body: TipPublish | None = None,
) -> TipPublishResponse:
    """Formata e despacha a tip, gravando um ``message_log`` por canal.

    Os canais são os **da banca** (ver Configurações), não os do ambiente.

    Uma falha de canal não é erro da requisição: ela vem no ``channels`` como
    ``failed``, com a linha correspondente no log — reenviar é decisão do admin.
    """
    tip = _get_owned_tip(session, tip_id, user)
    force = body.force if body is not None else False

    try:
        text, logs = tips_service.publish_tip(
            session, tip, senders=get_message_senders(tip.bankroll), force=force
        )
    except TipNotPublishable as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    session.commit()
    session.refresh(tip)

    return TipPublishResponse(
        tip=TipRead.model_validate(tip),
        message=text,
        channels=channels_of(logs),
    )
