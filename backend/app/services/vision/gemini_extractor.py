"""Extrator de tips usando a API de visão do Google Gemini."""

import random
import time
from collections.abc import Callable

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.tip import TipExtracted
from app.services.vision.base import VisionError, VisionExtractor
from app.services.vision.media import SUPPORTED_MEDIA_TYPES
from app.services.vision.prompts import SYSTEM_PROMPT, USER_PROMPT

logger = get_logger(__name__)

# Status HTTP que valem uma nova tentativa: pico de demanda no modelo (503) e
# rate limit (429). O resto — 400, 401, 404 — não melhora tentando de novo.
_TRANSIENT_STATUS_CODES = frozenset({429, 503})

# Resolução de mídia por nome de configuração. "default" fica de fora: não
# mandar o parâmetro é diferente de mandar UNSPECIFIED.
_MEDIA_RESOLUTIONS = {
    "low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
    "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
    "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
}

# finish_reason que significam "o modelo se recusou / foi barrado", não "deu erro".
_BLOCKED_FINISH_REASONS = frozenset(
    {
        types.FinishReason.SAFETY,
        types.FinishReason.PROHIBITED_CONTENT,
        types.FinishReason.BLOCKLIST,
        types.FinishReason.IMAGE_SAFETY,
        types.FinishReason.IMAGE_PROHIBITED_CONTENT,
        types.FinishReason.SPII,
        types.FinishReason.RECITATION,
    }
)


class GeminiVisionExtractor(VisionExtractor):
    """Lê a tip com structured outputs — o schema vira response_schema na chamada."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: genai.Client | None = None,
        max_attempts: int | None = None,
        retry_base_delay: float | None = None,
        media_resolution: str | None = None,
        timeout_seconds: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.vision_model
        self._media_resolution = _MEDIA_RESOLUTIONS.get(
            (media_resolution or settings.vision_media_resolution).lower()
        )
        self._max_attempts = max(
            1, max_attempts if max_attempts is not None else settings.vision_max_attempts
        )
        self._retry_base_delay = (
            retry_base_delay if retry_base_delay is not None else settings.vision_retry_base_delay
        )
        self._sleep = sleep
        self._timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.vision_timeout_seconds
        )

        if client is not None:
            self._client = client
            return

        # O SDK aceita cliente sem chave e só falha lá na chamada, com TypeError —
        # que não é APIError e escaparia do tratamento de erro do extract().
        key = api_key or settings.vision_api_key
        if not key:
            raise VisionError(
                "Nenhuma chave de API configurada. Defina VISION_API_KEY no .env "
                "(ou GOOGLE_API_KEY no ambiente)."
            )
        self._client = genai.Client(
            api_key=key,
            # o SDK conta em milissegundos
            http_options=types.HttpOptions(timeout=int(self._timeout_seconds * 1000)),
        )

    def extract(self, image: bytes, media_type: str) -> TipExtracted:
        if media_type not in SUPPORTED_MEDIA_TYPES:
            raise VisionError(f"Media type não suportado pela API de visão: {media_type}")

        response = self._generate_with_retry(image, media_type)

        # O prompt inteiro pode ser barrado antes de gerar qualquer candidate.
        block_reason = getattr(response.prompt_feedback, "block_reason", None)
        if block_reason is not None:
            raise VisionError(f"A API recusou processar a imagem ({block_reason}).")

        finish_reason = response.candidates[0].finish_reason if response.candidates else None
        if finish_reason in _BLOCKED_FINISH_REASONS:
            raise VisionError(f"A API recusou processar a imagem ({finish_reason}).")

        extracted = response.parsed
        if not isinstance(extracted, TipExtracted):
            raise VisionError(
                f"A API não devolveu um resultado válido (finish_reason={finish_reason})."
            )

        usage = response.usage_metadata
        logger.info(
            "vision.extracted",
            extra={
                "model": self.model,
                "media_resolution": (
                    self._media_resolution.name if self._media_resolution else "default"
                ),
                "complete": extracted.is_complete,
                "missing_fields": extracted.missing_fields,
                "input_tokens": getattr(usage, "prompt_token_count", None),
                "output_tokens": getattr(usage, "candidates_token_count", None),
            },
        )
        return extracted

    def _generate_with_retry(self, image: bytes, media_type: str):
        """Chama a API, repetindo com backoff enquanto o erro for transitório.

        503 ("model is currently experiencing high demand") e 429 reprovariam o
        print à toa — o print está bom, o servidor é que estava ocupado.
        """
        for attempt in range(1, self._max_attempts + 1):
            try:
                return self._client.models.generate_content(
                    model=self.model,
                    contents=[
                        types.Part.from_bytes(data=image, mime_type=media_type),
                        types.Part.from_text(text=USER_PROMPT),
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=TipExtracted,
                        max_output_tokens=4096,
                        # menos tokens de imagem = resposta mais rápida; None deixa
                        # o provedor decidir (ver VISION_MEDIA_RESOLUTION no .env)
                        media_resolution=self._media_resolution,
                        # não usamos tools; sem isto o SDK avisa sobre AFC a cada chamada
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                    ),
                )
            except httpx.TimeoutException as exc:
                # NÃO é APIError: sem este ramo o timeout escaparia do extract()
                # e derrubaria a requisição em vez de virar tip para revisão.
                if attempt == self._max_attempts:
                    raise VisionError(
                        f"A API de visão não respondeu em {self._timeout_seconds:g}s."
                    ) from exc

                delay = self._backoff_delay(attempt)
                logger.warning(
                    "vision.retry",
                    extra={
                        "model": self.model,
                        "attempt": attempt,
                        "max_attempts": self._max_attempts,
                        "status": "timeout",
                        "delay_seconds": round(delay, 2),
                    },
                )
                self._sleep(delay)

            except genai_errors.APIError as exc:
                is_last = attempt == self._max_attempts
                if exc.code not in _TRANSIENT_STATUS_CODES or is_last:
                    raise VisionError(f"Falha na chamada à API de visão: {exc}") from exc

                delay = self._backoff_delay(attempt)
                logger.warning(
                    "vision.retry",
                    extra={
                        "model": self.model,
                        "attempt": attempt,
                        "max_attempts": self._max_attempts,
                        "status": exc.code,
                        "delay_seconds": round(delay, 2),
                    },
                )
                self._sleep(delay)

        # inalcançável: o loop sempre retorna ou levanta na última tentativa
        raise VisionError("Falha na chamada à API de visão.")

    def _backoff_delay(self, attempt: int) -> float:
        """Backoff exponencial com jitter, para não repetir todos juntos."""
        return self._retry_base_delay * (2 ** (attempt - 1)) * (1 + random.random())
