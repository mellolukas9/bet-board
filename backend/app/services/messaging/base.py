"""Contrato de qualquer canal de envio de mensagem."""

from abc import ABC, abstractmethod

from app.models.tip import Channel


class MessageSendError(RuntimeError):
    """Falha ao entregar a mensagem no canal (rede, auth, canal inválido)."""


class MessageSender(ABC):
    """Envia o texto já formatado para um canal.

    O sender **não** formata nada — recebe a mensagem pronta do
    ``format_tip_message``. Cada canal só cuida do próprio transporte.
    """

    #: canal que este sender representa, para o registro em ``message_log``
    channel: Channel

    @abstractmethod
    def send(
        self,
        text: str,
        *,
        image: bytes | None = None,
        media_type: str | None = None,
    ) -> None:
        """Entrega a mensagem, com o print junto quando houver.

        A imagem é opcional: tip antiga (anterior à coluna ``raw_image``) ou
        canal que não suporta mídia continuam mandando só o texto.

        Raises:
            MessageSendError: quando a entrega falhou. O chamador registra a
                falha em ``message_log`` e segue com os outros canais.
        """
        raise NotImplementedError
