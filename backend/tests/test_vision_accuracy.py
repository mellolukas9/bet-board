"""Mede a taxa de acerto da IA de visão nos prints reais de ``tests/fixtures/prints``.

Chama a API de verdade (custa dinheiro), então roda só sob demanda:

    pytest -m vision

Como adicionar um caso: coloque o print (``.png``/``.jpg``/...) e um ``.json`` de
mesmo nome com os valores esperados. Veja ``tests/fixtures/prints/README.md``.
"""

import json
import os
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.vision import detect_media_type, get_vision_extractor

FIXTURES = Path(__file__).parent / "fixtures" / "prints"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
COMPARED_FIELDS = ("source", "event", "market", "odd", "stake", "currency")

# Piso da taxa de acerto agregada; ajuste conforme a base de fixtures cresce.
MIN_ACCURACY = float(os.getenv("VISION_MIN_ACCURACY", "0.90"))

pytestmark = pytest.mark.vision


def _cases() -> list[tuple[Path, Path]]:
    if not FIXTURES.is_dir():
        return []
    return sorted(
        (image, image.with_suffix(".json"))
        for image in FIXTURES.iterdir()
        if image.suffix.lower() in IMAGE_SUFFIXES and image.with_suffix(".json").is_file()
    )


def _normalize(field: str, value: object) -> object:
    if value is None:
        return None
    if field in ("odd", "stake"):
        # tolera 1.85 vs "1,85" vs Decimal("1.850")
        text = str(value).replace(",", ".")
        return Decimal(text).normalize()
    return " ".join(str(value).split()).casefold()


def _matches(field: str, expected: object, actual: object) -> bool:
    return _normalize(field, expected) == _normalize(field, actual)


@pytest.mark.skipif(not _cases(), reason="nenhum fixture de print com .json esperado")
def test_extraction_accuracy_on_real_prints(capsys: pytest.CaptureFixture[str]) -> None:
    extractor = get_vision_extractor()

    hits = 0
    total = 0
    report: list[str] = []

    for image_path, expected_path in _cases():
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        data = image_path.read_bytes()
        actual = extractor.extract(data, detect_media_type(data, image_path.name))

        wrong: list[str] = []
        for field in COMPARED_FIELDS:
            if field not in expected:
                continue  # o fixture não afirma nada sobre este campo
            total += 1
            actual_value = getattr(actual, field)
            if _matches(field, expected[field], actual_value):
                hits += 1
            else:
                wrong.append(f"{field}: esperado {expected[field]!r}, veio {actual_value!r}")

        status = "OK" if not wrong else "; ".join(wrong)
        report.append(f"  {image_path.name}: {status}")

    accuracy = hits / total if total else 0.0

    with capsys.disabled():
        print(f"\nTaxa de acerto: {hits}/{total} = {accuracy:.1%}")
        print("\n".join(report))

    assert total > 0, "os .json esperados não declararam nenhum campo comparável"
    assert accuracy >= MIN_ACCURACY, (
        f"taxa de acerto {accuracy:.1%} abaixo do piso {MIN_ACCURACY:.1%}"
    )
