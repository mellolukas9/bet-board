"""Serviço de visão: extração da tip a partir do print."""

from functools import lru_cache

from app.config import get_settings
from app.services.vision.base import VisionError, VisionExtractor
from app.services.vision.media import (
    SUPPORTED_MEDIA_TYPES,
    UnsupportedImageError,
    detect_media_type,
)

__all__ = [
    "SUPPORTED_MEDIA_TYPES",
    "UnsupportedImageError",
    "VisionError",
    "VisionExtractor",
    "detect_media_type",
    "get_vision_extractor",
]


@lru_cache
def get_vision_extractor() -> VisionExtractor:
    """Resolve o provedor configurado em ``VISION_PROVIDER``."""
    provider = get_settings().vision_provider.lower()

    if provider == "anthropic":
        # import tardio: só carrega o SDK do provedor realmente usado
        from app.services.vision.anthropic_extractor import AnthropicVisionExtractor

        return AnthropicVisionExtractor()

    if provider == "gemini":
        from app.services.vision.gemini_extractor import GeminiVisionExtractor

        return GeminiVisionExtractor()

    raise ValueError(
        f"Provedor de visão desconhecido: {provider!r}. Use 'gemini' ou 'anthropic'."
    )
