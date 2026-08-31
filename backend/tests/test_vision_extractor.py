"""Testes do extrator Anthropic com um cliente falso — não chamam a API."""

from types import SimpleNamespace

import anthropic
import pytest

from app.schemas.tip import TipExtracted
from app.services.vision.anthropic_extractor import AnthropicVisionExtractor
from app.services.vision.base import VisionError

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

COMPLETE = TipExtracted(
    source="Bet365",
    event="Flamengo x Palmeiras",
    market="Over 2.5 gols",
    odd=1.85,
    stake=50.0,
    currency="BRL",
    unreadable_reason=None,
)


class FakeMessages:
    def __init__(self, response) -> None:
        self._response = response
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class FakeClient:
    def __init__(self, response) -> None:
        self.messages = FakeMessages(response)


def make_response(parsed, stop_reason="end_turn"):
    return SimpleNamespace(
        parsed_output=parsed,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=1200, output_tokens=90),
    )


def make_extractor(response) -> tuple[AnthropicVisionExtractor, FakeClient]:
    client = FakeClient(response)
    return AnthropicVisionExtractor(model="claude-opus-5", client=client), client


def test_returns_the_parsed_tip() -> None:
    extractor, _ = make_extractor(make_response(COMPLETE))

    assert extractor.extract(PNG, "image/png") == COMPLETE


def test_sends_the_image_as_base64_with_the_declared_media_type() -> None:
    extractor, client = make_extractor(make_response(COMPLETE))

    extractor.extract(PNG, "image/png")

    content = client.messages.calls[0]["messages"][0]["content"]
    image_block = next(b for b in content if b["type"] == "image")
    assert image_block["source"]["media_type"] == "image/png"
    assert image_block["source"]["type"] == "base64"
    assert isinstance(image_block["source"]["data"], str)


def test_unreadable_print_is_a_normal_result_not_an_exception() -> None:
    unreadable = COMPLETE.model_copy(
        update={
            "source": None,
            "event": None,
            "market": None,
            "odd": None,
            "stake": None,
            "unreadable_reason": "Print cortado",
        }
    )
    extractor, _ = make_extractor(make_response(unreadable))

    result = extractor.extract(PNG, "image/png")

    assert result.unreadable_reason == "Print cortado"
    assert not result.is_complete


def test_rejects_unsupported_media_type_before_calling_the_api() -> None:
    extractor, client = make_extractor(make_response(COMPLETE))

    with pytest.raises(VisionError, match="não suportado"):
        extractor.extract(PNG, "image/bmp")

    assert client.messages.calls == []


def test_refusal_becomes_a_vision_error() -> None:
    extractor, _ = make_extractor(make_response(None, stop_reason="refusal"))

    with pytest.raises(VisionError, match="recusou"):
        extractor.extract(PNG, "image/png")


def test_missing_parsed_output_becomes_a_vision_error() -> None:
    extractor, _ = make_extractor(make_response(None, stop_reason="max_tokens"))

    with pytest.raises(VisionError, match="max_tokens"):
        extractor.extract(PNG, "image/png")


def test_api_errors_are_wrapped() -> None:
    failure = anthropic.APIConnectionError(request=None)
    extractor, _ = make_extractor(failure)

    with pytest.raises(VisionError, match="Falha na chamada"):
        extractor.extract(PNG, "image/png")
