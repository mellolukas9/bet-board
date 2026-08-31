"""Envio de mensagens pelo Telegram Bot API."""

import httpx

from app.core.logging import get_logger
from app.models.tip import Channel
from app.services.messaging.base import MessageSender, MessageSendError

logger = get_logger(__name__)

API_BASE = "https://api.telegram.org"
TIMEOUT_SECONDS = 15.0

# O caption do sendPhoto aceita bem menos que uma mensagem de texto (4096).
# Passando disso, a foto vai sem legenda e o texto vem logo atrás.
CAPTION_LIMIT = 1024


class TelegramSender(MessageSender):
    """Manda a mensagem para um canal/grupo via Bot API.

    Usa ``parse_mode=Markdown`` porque é o que o ``format_tip_message`` produz
    (``*negrito*``).
    """

    channel = Channel.TELEGRAM

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._client = client

        if not self._bot_token or not self._chat_id:
            raise MessageSendError(
                "Telegram não configurado nesta banca. Preencha o token do bot e "
                "o canal em Configurações."
            )

    def send(
        self,
        text: str,
        *,
        image: bytes | None = None,
        media_type: str | None = None,
    ) -> None:
        """Manda a tip; com o print junto quando ele existe.

        Sem imagem é ``sendMessage``, como sempre foi. Com imagem é
        ``sendPhoto``, e o texto vira legenda — a não ser que ele passe do
        limite de legenda, caso em que a foto vai sem legenda e o texto sai
        numa segunda mensagem, para não truncar a tip.
        """
        if image is None:
            self._send_message(text)
        else:
            cabe_na_legenda = len(text) <= CAPTION_LIMIT
            self._send_photo(image, media_type, caption=text if cabe_na_legenda else None)
            if not cabe_na_legenda:
                self._send_message(text)

        logger.info(
            "messaging.sent",
            extra={"channel": self.channel.value, "with_photo": image is not None},
        )

    def _send_message(self, text: str) -> None:
        self._post(
            "sendMessage",
            json={
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
        )

    def _send_photo(self, image: bytes, media_type: str | None, *, caption: str | None) -> None:
        data = {"chat_id": self._chat_id}
        if caption is not None:
            data["caption"] = caption
            data["parse_mode"] = "Markdown"

        # multipart: o Telegram aceita a foto como upload direto, sem precisar
        # de URL pública nem de hospedar o print em lugar nenhum
        self._post(
            "sendPhoto",
            data=data,
            files={"photo": ("print", image, media_type or "application/octet-stream")},
        )

    def _post(self, method: str, **kwargs) -> None:
        """Chama a Bot API e traduz qualquer recusa em ``MessageSendError``."""
        url = f"{API_BASE}/bot{self._bot_token}/{method}"

        try:
            if self._client is not None:
                response = self._client.post(url, **kwargs)
            else:
                with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                    response = client.post(url, **kwargs)
        except httpx.HTTPError as exc:
            raise MessageSendError(f"Falha de rede ao falar com o Telegram: {exc}") from exc

        if response.status_code != httpx.codes.OK:
            # o Telegram devolve o motivo em `description`; é o que ajuda a debugar
            detail = _describe(response)
            raise MessageSendError(f"Telegram recusou o envio ({response.status_code}): {detail}")

        body = response.json()
        if not body.get("ok"):
            raise MessageSendError(f"Telegram recusou o envio: {body.get('description')}")


def _describe(response: httpx.Response) -> str:
    try:
        return str(response.json().get("description", response.text))
    except ValueError:
        return response.text
