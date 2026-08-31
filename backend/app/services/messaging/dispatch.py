"""Despacho da mensagem nos canais + registro em ``message_log``."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.tip import Channel, MessageLog, MessageStatus
from app.services.messaging.base import MessageSender, MessageSendError

logger = get_logger(__name__)


def dispatch_tip_message(
    session: Session,
    *,
    tip_id: int,
    text: str,
    senders: list[MessageSender],
    image: bytes | None = None,
    media_type: str | None = None,
) -> list[MessageLog]:
    """Manda o texto por cada canal e registra o resultado de cada um.

    A falha de um canal **não** impede os outros: cada envio vira uma linha em
    ``message_log`` com ``sent`` ou ``failed``. Quem chama decide o que fazer com
    o resultado — reenviar é problema de outra camada.

    Não faz commit: a transação é de quem chamou.
    """
    logs: list[MessageLog] = []

    for sender in senders:
        try:
            sender.send(text, image=image, media_type=media_type)
        except MessageSendError as exc:
            logger.warning(
                "messaging.failed",
                extra={"tip_id": tip_id, "channel": sender.channel.value, "error": str(exc)},
            )
            log = MessageLog(
                tip_id=tip_id,
                channel=sender.channel,
                status=MessageStatus.FAILED,
                error=str(exc),
            )
        else:
            log = MessageLog(
                tip_id=tip_id,
                channel=sender.channel,
                status=MessageStatus.SENT,
                sent_at=datetime.now(UTC),
            )

        session.add(log)
        logs.append(log)

    return logs


def channels_of(logs: list[MessageLog]) -> dict[Channel, MessageStatus]:
    """Resumo canal -> status, para a resposta da API."""
    return {log.channel: log.status for log in logs}
