"""Logging estruturado (JSON) para a aplicação."""

import json
import logging
import sys
from datetime import UTC, datetime

_RESERVED = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
) | {"asctime", "message", "taskName"}


class JsonFormatter(logging.Formatter):
    """Formata cada registro como uma linha JSON.

    Qualquer campo extra passado via ``logger.info("msg", extra={...})`` entra no
    payload, o que permite correlacionar eventos do pipeline (tip_id, canal, etc.).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Instala o handler JSON na raiz, substituindo qualquer handler anterior."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # uvicorn instala os próprios handlers; delega para a raiz.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
