import json
import logging

from app.core.logging import JsonFormatter


def _record(**extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="tip.extracted", args=None, exc_info=None,
    )
    record.__dict__.update(extra)
    return record


def test_formats_as_json_with_core_fields() -> None:
    payload = json.loads(JsonFormatter().format(_record()))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["message"] == "tip.extracted"
    assert "ts" in payload


def test_includes_extra_fields() -> None:
    payload = json.loads(JsonFormatter().format(_record(tip_id=42, channel="telegram")))

    assert payload["tip_id"] == 42
    assert payload["channel"] == "telegram"
