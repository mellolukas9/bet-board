"""Mensageria: monta o texto da tip e entrega nos canais configurados.

Os canais são configurados **por banca** (ver ``Bankroll.telegram_*``), não no
ambiente: um servidor atende vários clientes, cada um com o seu grupo.
"""

from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.messaging.base import MessageSender, MessageSendError
from app.services.messaging.dispatch import channels_of, dispatch_tip_message
from app.services.messaging.formatter import (
    format_money,
    format_odd,
    format_tip_message,
    format_units,
)

if TYPE_CHECKING:
    from app.models.user import Bankroll

__all__ = [
    "MessageSendError",
    "MessageSender",
    "channels_of",
    "dispatch_tip_message",
    "format_money",
    "format_odd",
    "format_tip_message",
    "format_units",
    "get_message_senders",
]

logger = get_logger(__name__)


def get_message_senders(bankroll: "Bankroll") -> list[MessageSender]:
    """Devolve os senders configurados **nesta banca**.

    As credenciais saíam do ``.env``, o que amarrava o deploy inteiro a um
    cliente. Agora cada banca tem o seu canal, e o mesmo servidor atende vários
    tipsters sem que um enxergue o canal do outro.

    Canal sem credencial é **omitido**, não quebra: dá para rodar só no Telegram
    enquanto o webhook do WhatsApp não está de pé, e vice-versa. Lista vazia
    significa nenhum canal configurado — quem chama decide se isso é erro.
    """
    senders: list[MessageSender] = []

    # import tardio para o módulo não exigir httpx configurado só por ser importado
    from app.services.messaging.telegram import TelegramSender
    from app.services.messaging.whatsapp import WhatsAppSender

    construtores = (
        (
            "telegram",
            lambda: TelegramSender(
                bot_token=bankroll.telegram_bot_token or "",
                chat_id=bankroll.telegram_chat_id or "",
            ),
        ),
        (
            "whatsapp",
            lambda: WhatsAppSender(webhook_url=bankroll.whatsapp_webhook_url or ""),
        ),
    )

    for channel, build in construtores:
        try:
            senders.append(build())
        except MessageSendError as exc:
            logger.info(
                "messaging.channel_disabled",
                extra={
                    "channel": channel,
                    "bankroll_id": bankroll.id,
                    "reason": str(exc),
                },
            )

    return senders
