"""Testes do despacho + registro em message_log, com session e senders falsos."""

from app.models.tip import Channel, MessageStatus
from app.services.messaging.base import MessageSender, MessageSendError
from app.services.messaging.dispatch import channels_of, dispatch_tip_message

TEXT = "🎯 *NOVA TIP*"


class FakeSession:
    """Coleta o que seria persistido — dispatch não faz commit."""

    def __init__(self) -> None:
        self.added: list = []
        self.committed = False

    def add(self, obj) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.committed = True


class FakeSender(MessageSender):
    def __init__(self, channel: Channel, fail: str | None = None) -> None:
        self.channel = channel
        self.fail = fail
        self.sent: list[str] = []
        self.imagens: list[bytes | None] = []

    def send(
        self,
        text: str,
        *,
        image: bytes | None = None,
        media_type: str | None = None,
    ) -> None:
        if self.fail:
            raise MessageSendError(self.fail)
        self.sent.append(text)
        self.imagens.append(image)


def test_successful_send_is_logged_as_sent() -> None:
    session = FakeSession()
    sender = FakeSender(Channel.TELEGRAM)

    logs = dispatch_tip_message(session, tip_id=1, text=TEXT, senders=[sender])

    assert sender.sent == [TEXT]
    assert len(logs) == 1
    assert logs[0].status is MessageStatus.SENT
    assert logs[0].channel is Channel.TELEGRAM
    assert logs[0].tip_id == 1
    assert logs[0].sent_at is not None
    assert logs[0].error is None


def test_failed_send_is_logged_with_the_reason() -> None:
    session = FakeSession()
    sender = FakeSender(Channel.TELEGRAM, fail="chat not found")

    logs = dispatch_tip_message(session, tip_id=2, text=TEXT, senders=[sender])

    assert logs[0].status is MessageStatus.FAILED
    assert logs[0].error == "chat not found"
    assert logs[0].sent_at is None


def test_one_channel_failing_does_not_stop_the_others() -> None:
    session = FakeSession()
    telegram = FakeSender(Channel.TELEGRAM, fail="bot bloqueado")
    whatsapp = FakeSender(Channel.WHATSAPP)

    logs = dispatch_tip_message(
        session, tip_id=3, text=TEXT, senders=[telegram, whatsapp]
    )

    assert whatsapp.sent == [TEXT]
    assert channels_of(logs) == {
        Channel.TELEGRAM: MessageStatus.FAILED,
        Channel.WHATSAPP: MessageStatus.SENT,
    }


def test_every_log_is_staged_in_the_session() -> None:
    session = FakeSession()
    senders = [FakeSender(Channel.TELEGRAM), FakeSender(Channel.WHATSAPP)]

    logs = dispatch_tip_message(session, tip_id=4, text=TEXT, senders=senders)

    assert session.added == logs


def test_dispatch_does_not_commit() -> None:
    """A transação é de quem chamou — dispatch só monta as linhas."""
    session = FakeSession()

    dispatch_tip_message(session, tip_id=5, text=TEXT, senders=[FakeSender(Channel.TELEGRAM)])

    assert session.committed is False


def test_no_senders_configured_logs_nothing() -> None:
    session = FakeSession()

    logs = dispatch_tip_message(session, tip_id=6, text=TEXT, senders=[])

    assert logs == []
    assert session.added == []
