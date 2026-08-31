"""Envio de mensagens pelo WhatsApp, via webhook do n8n / Evolution."""

import base64

import httpx

from app.core.logging import get_logger
from app.models.tip import Channel
from app.services.messaging.base import MessageSender, MessageSendError

logger = get_logger(__name__)

TIMEOUT_SECONDS = 20.0


class WhatsAppSender(MessageSender):
    """Dispara a mensagem para um webhook que entrega no WhatsApp.

    O backend não fala com o WhatsApp direto: manda um ``POST`` com a mensagem
    pronta para o n8n, e o workflow de lá cuida da Evolution API (instância,
    número de destino, formatação da sessão). Por isso o payload é mínimo —
    ``{"text": ...}`` — e o destino é problema do fluxo no n8n, não daqui.

    Qualquer 2xx conta como entregue: webhook de n8n costuma responder 200 com
    corpo vazio ou 202 quando o workflow roda em modo assíncrono.
    """

    channel = Channel.WHATSAPP

    def __init__(
        self,
        *,
        webhook_url: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._client = client

        if not self._webhook_url:
            raise MessageSendError(
                "WhatsApp não configurado nesta banca. Preencha o webhook em "
                "Configurações."
            )

    def send(
        self,
        text: str,
        *,
        image: bytes | None = None,
        media_type: str | None = None,
    ) -> None:
        payload: dict[str, str] = {"text": text}

        # base64 porque o payload é JSON; o workflow no n8n decodifica e passa
        # para a Evolution como mídia. Sem imagem, o campo nem aparece.
        if image is not None:
            payload["image_base64"] = base64.b64encode(image).decode("ascii")
            payload["image_media_type"] = media_type or "application/octet-stream"

        try:
            if self._client is not None:
                response = self._client.post(self._webhook_url, json=payload)
            else:
                with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                    response = client.post(self._webhook_url, json=payload)
        except httpx.HTTPError as exc:
            raise MessageSendError(f"Falha de rede ao falar com o webhook: {exc}") from exc

        if not response.is_success:
            raise MessageSendError(
                f"Webhook do WhatsApp recusou o envio ({response.status_code}): "
                f"{_describe(response)}"
            )

        logger.info("messaging.sent", extra={"channel": self.channel.value})


def _describe(response: httpx.Response) -> str:
    """Motivo da recusa, em uma linha — o n8n devolve JSON ou texto cru."""
    text = response.text.strip()
    return text[:300] if text else "sem corpo na resposta"
