"""Interface do extrator de tips a partir de imagem."""

from abc import ABC, abstractmethod

from app.schemas.tip import TipExtracted


class VisionError(RuntimeError):
    """Falha ao chamar o provedor de visão (rede, auth, quota, recusa)."""


class VisionExtractor(ABC):
    """Contrato de qualquer provedor de visão.

    Implementações NÃO devem levantar exceção por print ilegível ou campo
    faltando — isso é resultado normal e vem em ``TipExtracted``. Só levantam
    ``VisionError`` quando a chamada em si falhou.
    """

    @abstractmethod
    def extract(self, image: bytes, media_type: str) -> TipExtracted:
        """Lê o print e devolve a tip estruturada.

        Args:
            image: bytes da imagem.
            media_type: MIME type (image/png, image/jpeg, image/gif, image/webp).
        """
        raise NotImplementedError
