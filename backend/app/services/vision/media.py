"""Detecção do media type das imagens aceitas pela API de visão."""

from pathlib import Path

SUPPORTED_MEDIA_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)

_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# Assinaturas de bytes — mais confiáveis que a extensão, que o usuário controla.
_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


class UnsupportedImageError(ValueError):
    pass


def detect_media_type(data: bytes, filename: str | None = None) -> str:
    """Descobre o media type pelos bytes, caindo para a extensão do arquivo."""
    for magic, media_type in _MAGIC:
        if data.startswith(magic):
            return media_type

    # WEBP: "RIFF" + 4 bytes de tamanho + "WEBP"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"

    if filename:
        guess = _EXTENSIONS.get(Path(filename).suffix.lower())
        if guess:
            return guess

    raise UnsupportedImageError(
        "Formato de imagem não reconhecido. Aceitos: PNG, JPEG, GIF, WEBP."
    )
