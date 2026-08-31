import pytest

from app.services.vision.media import UnsupportedImageError, detect_media_type

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
GIF = b"GIF89a" + b"\x00" * 16
WEBP = b"RIFF\x24\x00\x00\x00WEBP" + b"\x00" * 8


@pytest.mark.parametrize(
    ("data", "expected"),
    [(PNG, "image/png"), (JPEG, "image/jpeg"), (GIF, "image/gif"), (WEBP, "image/webp")],
)
def test_detects_by_magic_bytes(data: bytes, expected: str) -> None:
    assert detect_media_type(data) == expected


def test_magic_bytes_win_over_a_wrong_extension() -> None:
    assert detect_media_type(PNG, "print.jpg") == "image/png"


def test_falls_back_to_extension_when_bytes_are_unknown() -> None:
    assert detect_media_type(b"\x00" * 32, "print.jpeg") == "image/jpeg"


def test_rejects_unknown_format() -> None:
    with pytest.raises(UnsupportedImageError):
        detect_media_type(b"\x00" * 32, "print.bmp")
