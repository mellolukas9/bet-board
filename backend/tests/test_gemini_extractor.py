"""Testes do extrator Gemini com um cliente falso — não chamam a API."""

from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app.schemas.tip import TipExtracted
from app.services.vision.base import VisionError
from app.services.vision.gemini_extractor import GeminiVisionExtractor

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

COMPLETE = TipExtracted(
    source="Bet365",
    matches=["Flamengo x Palmeiras"],
    market="Over 2.5 gols",
    odd=1.85,
    stake=50.0,
    currency="BRL",
    unreadable_reason=None,
)


class FakeModels:
    """Devolve a resposta dada; com uma lista, uma por chamada (para testar retry)."""

    def __init__(self, response) -> None:
        self._responses = list(response) if isinstance(response, list) else None
        self._response = response
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self._responses is not None:
            # a última se repete, para não estourar a lista em teste de retry
            item = self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]
        else:
            item = self._response
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, response) -> None:
        self.models = FakeModels(response)


def make_response(
    parsed,
    finish_reason=types.FinishReason.STOP,
    block_reason=None,
):
    return SimpleNamespace(
        parsed=parsed,
        candidates=[SimpleNamespace(finish_reason=finish_reason)],
        prompt_feedback=SimpleNamespace(block_reason=block_reason),
        usage_metadata=SimpleNamespace(prompt_token_count=1200, candidates_token_count=90),
    )


def make_extractor(
    response,
    *,
    max_attempts: int = 1,
    slept: list[float] | None = None,
    media_resolution: str = "default",
) -> tuple[GeminiVisionExtractor, FakeClient]:
    """Por padrão sem retry: cada teste que quer retry pede explicitamente.

    O ``sleep`` é falso — o teste não espera segundos de verdade.
    """
    client = FakeClient(response)
    extractor = GeminiVisionExtractor(
        model="models/gemini-3.5-flash-lite",
        client=client,
        max_attempts=max_attempts,
        retry_base_delay=0.01,
        media_resolution=media_resolution,
        sleep=slept.append if slept is not None else lambda _: None,
    )
    return extractor, client


def server_error(code: int, message: str = "indisponível") -> genai_errors.APIError:
    return genai_errors.APIError(code, {"error": {"message": message}})


def test_returns_the_parsed_tip() -> None:
    extractor, _ = make_extractor(make_response(COMPLETE))

    assert extractor.extract(PNG, "image/png") == COMPLETE


def test_sends_the_image_bytes_with_the_declared_media_type() -> None:
    extractor, client = make_extractor(make_response(COMPLETE))

    extractor.extract(PNG, "image/png")

    contents = client.models.calls[0]["contents"]
    image_part = next(p for p in contents if p.inline_data is not None)
    assert image_part.inline_data.mime_type == "image/png"
    assert image_part.inline_data.data == PNG


def test_asks_for_json_constrained_to_the_tip_schema() -> None:
    extractor, client = make_extractor(make_response(COMPLETE))

    extractor.extract(PNG, "image/png")

    config = client.models.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is TipExtracted


def test_uses_the_configured_model() -> None:
    extractor, client = make_extractor(make_response(COMPLETE))

    extractor.extract(PNG, "image/png")

    assert client.models.calls[0]["model"] == "models/gemini-3.5-flash-lite"


@pytest.mark.parametrize(
    ("configurado", "esperado"),
    [
        ("low", types.MediaResolution.MEDIA_RESOLUTION_LOW),
        ("medium", types.MediaResolution.MEDIA_RESOLUTION_MEDIUM),
        ("high", types.MediaResolution.MEDIA_RESOLUTION_HIGH),
    ],
)
def test_sends_the_configured_media_resolution(configurado, esperado) -> None:
    extractor, client = make_extractor(
        make_response(COMPLETE), media_resolution=configurado
    )

    extractor.extract(PNG, "image/png")

    assert client.models.calls[0]["config"].media_resolution is esperado


def test_default_media_resolution_omits_the_parameter() -> None:
    """Não mandar o parâmetro é diferente de mandar UNSPECIFIED."""
    extractor, client = make_extractor(
        make_response(COMPLETE), media_resolution="default"
    )

    extractor.extract(PNG, "image/png")

    assert client.models.calls[0]["config"].media_resolution is None


def test_unknown_media_resolution_falls_back_to_default() -> None:
    """Valor inválido não pode derrubar a leitura do print."""
    extractor, client = make_extractor(
        make_response(COMPLETE), media_resolution="altíssima"
    )

    extractor.extract(PNG, "image/png")

    assert client.models.calls[0]["config"].media_resolution is None


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

    assert client.models.calls == []


def test_blocked_prompt_becomes_a_vision_error() -> None:
    extractor, _ = make_extractor(
        make_response(None, block_reason=types.BlockedReason.SAFETY)
    )

    with pytest.raises(VisionError, match="recusou"):
        extractor.extract(PNG, "image/png")


def test_blocked_candidate_becomes_a_vision_error() -> None:
    extractor, _ = make_extractor(
        make_response(None, finish_reason=types.FinishReason.PROHIBITED_CONTENT)
    )

    with pytest.raises(VisionError, match="recusou"):
        extractor.extract(PNG, "image/png")


def test_missing_parsed_output_becomes_a_vision_error() -> None:
    extractor, _ = make_extractor(
        make_response(None, finish_reason=types.FinishReason.MAX_TOKENS)
    )

    with pytest.raises(VisionError, match="MAX_TOKENS"):
        extractor.extract(PNG, "image/png")


def test_api_errors_are_wrapped() -> None:
    failure = genai_errors.ServerError(503, {"error": {"message": "indisponível"}})
    extractor, _ = make_extractor(failure)

    with pytest.raises(VisionError, match="Falha na chamada"):
        extractor.extract(PNG, "image/png")


@pytest.mark.parametrize("code", [503, 429])
def test_transient_failure_is_retried_and_succeeds(code: int) -> None:
    """503/429 é pico de demanda do modelo, não print ruim — vale tentar de novo."""
    slept: list[float] = []
    extractor, client = make_extractor(
        [server_error(code), make_response(COMPLETE)], max_attempts=3, slept=slept
    )

    assert extractor.extract(PNG, "image/png") == COMPLETE
    assert len(client.models.calls) == 2
    assert len(slept) == 1


def test_retry_gives_up_after_max_attempts() -> None:
    slept: list[float] = []
    extractor, client = make_extractor(server_error(503), max_attempts=3, slept=slept)

    with pytest.raises(VisionError, match="Falha na chamada"):
        extractor.extract(PNG, "image/png")

    assert len(client.models.calls) == 3
    assert len(slept) == 2  # espera entre tentativas, não depois da última


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_permanent_failure_is_not_retried(code: int) -> None:
    """Chave errada ou requisição inválida não melhora tentando de novo."""
    extractor, client = make_extractor(server_error(code), max_attempts=3)

    with pytest.raises(VisionError, match="Falha na chamada"):
        extractor.extract(PNG, "image/png")

    assert len(client.models.calls) == 1


def test_backoff_grows_between_attempts() -> None:
    slept: list[float] = []
    extractor, _ = make_extractor(server_error(503), max_attempts=4, slept=slept)

    with pytest.raises(VisionError):
        extractor.extract(PNG, "image/png")

    # com jitter os valores variam, mas cada janela dobra: [b,2b] < [2b,4b] < [4b,8b]
    assert slept[0] < slept[1] < slept[2]


def test_missing_api_key_is_a_vision_error_not_a_crash(monkeypatch) -> None:
    """Sem chave o SDK só quebraria na chamada, com TypeError — barramos antes."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("VISION_API_KEY", "")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(VisionError, match="Nenhuma chave de API"):
        GeminiVisionExtractor()

    get_settings.cache_clear()


# --- timeout por tentativa ---------------------------------------------------


def test_timeout_is_retried_then_becomes_a_vision_error() -> None:
    """Timeout não é APIError; sem tratamento próprio ele escaparia do extract()."""
    slept: list[float] = []
    extractor, client = make_extractor(
        httpx.ReadTimeout("demorou demais"), max_attempts=3, slept=slept
    )

    with pytest.raises(VisionError, match="não respondeu"):
        extractor.extract(PNG, "image/png")

    assert len(client.models.calls) == 3
    assert len(slept) == 2


def test_timeout_that_recovers_returns_the_tip() -> None:
    extractor, _ = make_extractor(
        [httpx.ReadTimeout("demorou"), make_response(COMPLETE)], max_attempts=2
    )

    assert extractor.extract(PNG, "image/png") == COMPLETE
