"""Extrator de tips usando a API de visão da Anthropic."""

import base64

import anthropic

from app.config import get_settings
from app.core.logging import get_logger
from app.schemas.tip import TipExtracted
from app.services.vision.base import VisionError, VisionExtractor
from app.services.vision.media import SUPPORTED_MEDIA_TYPES
from app.services.vision.prompts import SYSTEM_PROMPT, USER_PROMPT

logger = get_logger(__name__)


class AnthropicVisionExtractor(VisionExtractor):
    """Lê a tip com structured outputs — a resposta já vem validada no schema."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        settings = get_settings()
        self.model = model or settings.vision_model
        self._client = client or anthropic.Anthropic(
            api_key=api_key or settings.vision_api_key or None
        )

    def extract(self, image: bytes, media_type: str) -> TipExtracted:
        if media_type not in SUPPORTED_MEDIA_TYPES:
            raise VisionError(f"Media type não suportado pela API de visão: {media_type}")

        encoded = base64.standard_b64encode(image).decode("utf-8")

        try:
            response = self._client.messages.parse(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": encoded,
                                },
                            },
                            {"type": "text", "text": USER_PROMPT},
                        ],
                    }
                ],
                output_format=TipExtracted,
            )
        except anthropic.APIError as exc:
            raise VisionError(f"Falha na chamada à API de visão: {exc}") from exc

        # Uma recusa é HTTP 200 com content vazio — precisa ser checada antes
        # de ler o resultado.
        if response.stop_reason == "refusal":
            raise VisionError("A API recusou processar a imagem.")

        extracted = response.parsed_output
        if extracted is None:
            raise VisionError(
                f"A API não devolveu um resultado válido (stop_reason={response.stop_reason})."
            )

        logger.info(
            "vision.extracted",
            extra={
                "model": self.model,
                "complete": extracted.is_complete,
                "missing_fields": extracted.missing_fields,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )
        return extracted
