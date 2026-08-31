"""Testes do WhatsAppSender com transporte falso — não saem da máquina."""

import base64
import json

import httpx
import pytest

from app.models.tip import Channel
from app.services.messaging.base import MessageSendError
from app.services.messaging.whatsapp import WhatsAppSender

TEXT = "🎯 *NOVA TIP*\n\n⚽ Flamengo x Palmeiras"
WEBHOOK = "https://n8n.exemplo.com/webhook/bet-board"


def make_sender(handler) -> WhatsAppSender:
    """Sender com httpx.MockTransport — nada vai para a rede."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return WhatsAppSender(webhook_url=WEBHOOK, client=client)


def test_posts_the_text_to_the_webhook() -> None:
    capturado: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        capturado["json"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    make_sender(handler).send(TEXT)

    assert capturado["url"] == WEBHOOK
    assert capturado["json"] == {"text": TEXT}


def test_declares_the_whatsapp_channel() -> None:
    assert WhatsAppSender(webhook_url=WEBHOOK).channel is Channel.WHATSAPP


def test_accepts_any_2xx() -> None:
    """n8n em modo assíncrono responde 202 com corpo vazio — é sucesso."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202)

    make_sender(handler).send(TEXT)


def test_http_error_becomes_message_send_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="webhook not registered")

    with pytest.raises(MessageSendError, match="webhook not registered"):
        make_sender(handler).send(TEXT)


def test_empty_error_body_still_reports_the_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(MessageSendError, match="500"):
        make_sender(handler).send(TEXT)


def test_network_failure_becomes_message_send_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota para o host")

    with pytest.raises(MessageSendError, match="Falha de rede"):
        make_sender(handler).send(TEXT)


def test_missing_webhook_fails_at_construction() -> None:
    with pytest.raises(MessageSendError, match="não configurado"):
        WhatsAppSender(webhook_url="")


# --- envio com o print junto ------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_sends_the_image_as_base64() -> None:
    capturado: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["json"] = json.loads(request.content)
        return httpx.Response(200)

    make_sender(handler).send(TEXT, image=PNG, media_type="image/png")

    assert capturado["json"]["text"] == TEXT
    assert base64.b64decode(capturado["json"]["image_base64"]) == PNG
    assert capturado["json"]["image_media_type"] == "image/png"


def test_omits_the_image_fields_when_there_is_none() -> None:
    """Sem print, o payload é o mesmo de antes — não quebra workflow existente."""
    capturado: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["json"] = json.loads(request.content)
        return httpx.Response(200)

    make_sender(handler).send(TEXT)

    assert capturado["json"] == {"text": TEXT}
