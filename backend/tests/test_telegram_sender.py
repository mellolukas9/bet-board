"""Testes do TelegramSender com transporte falso — não saem da máquina."""

import httpx
import pytest

from app.models.tip import Channel
from app.services.messaging.base import MessageSendError
from app.services.messaging.telegram import TelegramSender

TEXT = "🎯 *NOVA TIP*\n\n⚽ Flamengo x Palmeiras"


def make_sender(handler) -> TelegramSender:
    """Sender com httpx.MockTransport — nada vai para a rede."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return TelegramSender(bot_token="123:ABC", chat_id="-1001", client=client)


def test_posts_the_text_to_send_message() -> None:
    capturado: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        capturado["json"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    make_sender(handler).send(TEXT)

    assert capturado["url"].endswith("/bot123:ABC/sendMessage")
    assert capturado["json"]["chat_id"] == "-1001"
    assert capturado["json"]["text"] == TEXT
    assert capturado["json"]["parse_mode"] == "Markdown"


def test_declares_the_telegram_channel() -> None:
    assert TelegramSender(bot_token="x", chat_id="y").channel is Channel.TELEGRAM


def test_http_error_becomes_message_send_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"ok": False, "description": "chat not found"}
        )

    with pytest.raises(MessageSendError, match="chat not found"):
        make_sender(handler).send(TEXT)


def test_ok_false_with_status_200_still_fails() -> None:
    """O Telegram às vezes devolve 200 com ok=false — não é sucesso."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "bot was blocked"})

    with pytest.raises(MessageSendError, match="bot was blocked"):
        make_sender(handler).send(TEXT)


def test_network_failure_becomes_message_send_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota para o host")

    with pytest.raises(MessageSendError, match="Falha de rede"):
        make_sender(handler).send(TEXT)


def test_missing_credentials_fails_at_construction() -> None:
    with pytest.raises(MessageSendError, match="não configurado"):
        TelegramSender(bot_token="", chat_id="-1001")

    with pytest.raises(MessageSendError, match="não configurado"):
        TelegramSender(bot_token="123:ABC", chat_id="")


# --- envio com o print junto ------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_sends_photo_with_the_text_as_caption() -> None:
    capturado: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["url"] = str(request.url)
        capturado["body"] = request.content
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    make_sender(handler).send(TEXT, image=PNG, media_type="image/png")

    assert capturado["url"].endswith("/sendPhoto")
    # multipart: confere que a foto e a legenda foram ambas no corpo
    assert PNG in capturado["body"]
    assert TEXT.encode() in capturado["body"]


def test_sends_plain_message_when_there_is_no_image() -> None:
    """Tip antiga, sem print guardado, continua saindo como texto."""
    chamadas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    make_sender(handler).send(TEXT)

    assert len(chamadas) == 1
    assert chamadas[0].endswith("/sendMessage")


def test_long_text_goes_as_a_separate_message_after_the_photo() -> None:
    """Passando do limite de legenda, o texto não pode ser truncado."""
    longo = "x" * 1500
    chamadas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    make_sender(handler).send(longo, image=PNG, media_type="image/png")

    assert [c.rsplit("/", 1)[-1] for c in chamadas] == ["sendPhoto", "sendMessage"]


def test_photo_failure_becomes_message_send_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"ok": False, "description": "PHOTO_INVALID_DIMENSIONS"})

    with pytest.raises(MessageSendError, match="PHOTO_INVALID_DIMENSIONS"):
        make_sender(handler).send(TEXT, image=PNG, media_type="image/png")
