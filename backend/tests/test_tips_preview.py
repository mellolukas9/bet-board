"""Testes da rota POST /tips/preview com o extrator trocado por um falso."""

import pytest
from fastapi.testclient import TestClient

from app.schemas.tip import TipExtracted
from app.services.vision import get_vision_extractor
from app.services.vision.base import VisionError, VisionExtractor

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

COMPLETE = TipExtracted(
    source="bet365",
    matches=["Flamengo x Palmeiras"],
    market="Mais de 2.5 gols",
    odd=1.85,
    stake=150.0,
    currency="BRL",
    unreadable_reason=None,
)


class FakeExtractor(VisionExtractor):
    def __init__(self, result) -> None:
        self.result = result
        self.calls: list[tuple[int, str]] = []

    def extract(self, image: bytes, media_type: str) -> TipExtracted:
        self.calls.append((len(image), media_type))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def use_extractor(monkeypatch):
    """Injeta um extrator falso no lugar do provedor configurado."""

    def _use(result) -> FakeExtractor:
        fake = FakeExtractor(result)
        monkeypatch.setattr(
            "app.api.routes.tips.get_vision_extractor",
            lambda: fake,
        )
        return fake

    get_vision_extractor.cache_clear()
    yield _use
    get_vision_extractor.cache_clear()


def post_print(client: TestClient, data: bytes = PNG, filename: str = "print.png"):
    return client.post(
        "/tips/preview",
        files={"file": (filename, data, "image/png")},
    )


def test_returns_the_tip_and_the_formatted_message(client, use_extractor) -> None:
    use_extractor(COMPLETE)

    response = post_print(client)

    assert response.status_code == 200
    body = response.json()
    assert body["tip"]["event"] == "Flamengo x Palmeiras"
    assert body["is_complete"] is True
    assert body["needs_review"] is False
    assert body["missing_fields"] == []
    assert "R$ 150,00" in body["message"]
    assert "1,85" in body["message"]


def test_sends_the_detected_media_type_to_the_extractor(client, use_extractor) -> None:
    fake = use_extractor(COMPLETE)

    post_print(client)

    assert fake.calls == [(len(PNG), "image/png")]


def test_incomplete_tip_is_flagged_for_review_but_still_returns_a_message(
    client, use_extractor
) -> None:
    use_extractor(COMPLETE.model_copy(update={"stake": None}))

    body = post_print(client).json()

    assert body["needs_review"] is True
    assert body["missing_fields"] == ["stake"]
    assert body["message"] is not None
    assert "Stake" not in body["message"]


def test_unreadable_print_returns_no_message(client, use_extractor) -> None:
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
    use_extractor(unreadable)

    body = post_print(client).json()

    assert body["message"] is None
    assert body["needs_review"] is True
    assert body["tip"]["unreadable_reason"] == "Print cortado"


def test_empty_file_is_rejected(client, use_extractor) -> None:
    use_extractor(COMPLETE)

    response = post_print(client, data=b"")

    assert response.status_code == 400


def test_unsupported_format_is_rejected_before_calling_the_provider(
    client, use_extractor
) -> None:
    fake = use_extractor(COMPLETE)

    response = post_print(client, data=b"nao-e-imagem", filename="doc.txt")

    assert response.status_code == 415
    assert fake.calls == []


def test_provider_failure_becomes_502(client, use_extractor) -> None:
    use_extractor(VisionError("quota estourada"))

    response = post_print(client)

    assert response.status_code == 502
    assert "quota estourada" in response.json()["detail"]
