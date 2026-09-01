"""Testes de ponta a ponta da 1.5: POST /tips, GET, PATCH e publish.

Extrator e senders são falsos — nenhum teste aqui chama API externa. O banco é
o SQLite em memória do ``conftest``.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models.tip import Channel, MessageStatus, TipStatus
from app.schemas.tip import TipExtracted
from app.services.messaging.base import MessageSender, MessageSendError
from app.services.vision import get_vision_extractor
from app.services.vision.base import VisionError, VisionExtractor

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

COMPLETE = TipExtracted(
    source="bet365",
    matches=["Flamengo x Palmeiras"],
    market="Mais de 2.5 gols",
    odd=1.85,
    stake=150.0,
    currency="BRL",
    unreadable_reason=None,
)

INCOMPLETE = TipExtracted(
    source="bet365",
    matches=None,
    market=None,
    odd=None,
    stake=None,
    currency=None,
    unreadable_reason="print cortado",
)


class FakeExtractor(VisionExtractor):
    def __init__(self, result) -> None:
        self.result = result

    def extract(self, image: bytes, media_type: str) -> TipExtracted:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


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


@pytest.fixture
def use_extractor(monkeypatch):
    """Troca o provedor de visão por um falso nas duas rotas que o usam."""

    def _use(result) -> FakeExtractor:
        fake = FakeExtractor(result)
        monkeypatch.setattr("app.api.routes.tips.get_vision_extractor", lambda: fake)
        return fake

    get_vision_extractor.cache_clear()
    yield _use
    get_vision_extractor.cache_clear()


@pytest.fixture
def use_senders(monkeypatch):
    """Troca os canais reais por falsos — nada sai para o Telegram no teste."""

    def _use(*senders: MessageSender) -> list[MessageSender]:
        chosen = list(senders)
        # a assinatura recebe a banca desde a multi-tenancy; o teste ignora qual
        monkeypatch.setattr(
            "app.api.routes.tips.get_message_senders", lambda _bankroll: chosen
        )
        return chosen

    return _use


def create_tip(client: TestClient, bankroll, filename: str = "print.png"):
    return client.post(
        f"/bankrolls/{bankroll.id}/tips", files={"file": (filename, PNG, "image/png")}
    )


def money(value: str | None) -> Decimal | None:
    """Compara valor numerico sem depender da escala do banco.

    O Postgres devolve Numeric(8,3) como "1.850"; o SQLite dos testes, "1.85".
    """
    return None if value is None else Decimal(value)


def make_publishable(client: TestClient, tip_id: int, units: str = "2") -> None:
    """Completa o que a IA não tem como saber: o stake em unidades."""
    response = client.patch(f"/tips/{tip_id}", json={"stake_units": units})
    assert response.status_code == 200


# --- POST /tips ---------------------------------------------------------------


def test_creates_the_tip_from_the_print(client, bankroll, use_extractor) -> None:
    use_extractor(COMPLETE)

    response = create_tip(client, bankroll)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["event"] == "Flamengo x Palmeiras"
    assert money(body["odd"]) == Decimal("1.85")
    assert money(body["stake"]) == Decimal("150")
    assert body["status"] == TipStatus.PENDING.value
    assert body["raw_image_ref"] == "print.png"
    assert body["extracted_at"] is not None


def test_new_tip_always_needs_review_because_units_are_manual(
    client,
    bankroll,
    use_extractor,
) -> None:
    """Mesmo com o print lido inteiro falta o stake em unidades, que só o admin sabe."""
    use_extractor(COMPLETE)

    body = create_tip(client, bankroll).json()

    assert body["stake_units"] is None
    assert body["needs_review"] is True


def test_unreadable_print_is_persisted_for_manual_review(client, bankroll, use_extractor) -> None:
    use_extractor(INCOMPLETE)

    body = create_tip(client, bankroll).json()

    assert body["needs_review"] is True
    assert body["extraction_error"] == "print cortado"
    assert body["event"] is None


def test_provider_failure_does_not_lose_the_tip(client, bankroll, use_extractor) -> None:
    """Se o Gemini cair, o print não pode ser perdido — vira tip para completar à mão."""
    use_extractor(VisionError("503 UNAVAILABLE"))

    response = create_tip(client, bankroll)

    assert response.status_code == 201
    body = response.json()
    assert body["needs_review"] is True
    assert "503" in body["extraction_error"]


def test_rejects_a_file_that_is_not_an_image(client, bankroll, use_extractor) -> None:
    use_extractor(COMPLETE)

    response = client.post(
        f"/bankrolls/{bankroll.id}/tips",
        files={"file": ("nota.txt", b"nao sou imagem", "text/plain")},
    )

    assert response.status_code == 415


# --- GET /tips ----------------------------------------------------------------


def test_lists_tips_newest_first(client, bankroll, use_extractor) -> None:
    use_extractor(COMPLETE)
    first = create_tip(client, bankroll).json()["id"]
    second = create_tip(client, bankroll).json()["id"]

    body = client.get(f"/bankrolls/{bankroll.id}/tips").json()

    assert [t["id"] for t in body] == [second, first]


def test_filters_the_manual_review_queue(client, bankroll, use_extractor) -> None:
    use_extractor(COMPLETE)
    pendente = create_tip(client, bankroll).json()["id"]
    revisada = create_tip(client, bankroll).json()["id"]
    make_publishable(client, revisada)

    em_revisao = client.get(f"/bankrolls/{bankroll.id}/tips", params={"needs_review": True}).json()

    assert [t["id"] for t in em_revisao] == [pendente]


def test_filters_by_status(client, bankroll, use_extractor) -> None:
    use_extractor(COMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]

    pendentes = client.get(
        f"/bankrolls/{bankroll.id}/tips", params={"status": "pending"}
    ).json()
    assert pendentes[0]["id"] == tip_id
    assert client.get(f"/bankrolls/{bankroll.id}/tips", params={"status": "green"}).json() == []


def test_reads_one_tip(client, bankroll, use_extractor) -> None:
    use_extractor(COMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]

    body = client.get(f"/tips/{tip_id}").json()

    assert body["id"] == tip_id
    assert body["messages"] == []


def test_unknown_tip_is_404(client) -> None:
    assert client.get("/tips/999").status_code == 404


# --- PATCH /tips/{id} ---------------------------------------------------------


def test_patch_corrects_a_badly_read_tip(client, bankroll, use_extractor) -> None:
    use_extractor(INCOMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]

    body = client.patch(
        f"/tips/{tip_id}",
        json={"event": "Grêmio x Internacional", "market": "Ambas marcam", "odd": "1.72"},
    ).json()

    assert body["event"] == "Grêmio x Internacional"
    assert money(body["odd"]) == Decimal("1.72")
    assert body["source"] == "bet365"  # não enviado no PATCH, permanece


def test_patch_only_touches_the_fields_sent(client, bankroll, use_extractor) -> None:
    use_extractor(COMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]

    body = client.patch(f"/tips/{tip_id}", json={"market": "Menos de 3.5 gols"}).json()

    assert body["market"] == "Menos de 3.5 gols"
    assert body["event"] == "Flamengo x Palmeiras"
    assert money(body["stake"]) == Decimal("150")


def test_informing_the_units_takes_the_tip_out_of_the_queue(
    client,
    bankroll,
    use_extractor,
) -> None:
    use_extractor(COMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]

    body = client.patch(f"/tips/{tip_id}", json={"stake_units": "2"}).json()

    assert money(body["stake_units"]) == Decimal("2")
    assert body["needs_review"] is False


def test_tip_still_missing_fields_stays_in_the_queue(client, bankroll, use_extractor) -> None:
    use_extractor(INCOMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]

    body = client.patch(f"/tips/{tip_id}", json={"stake_units": "1.5"}).json()

    assert body["needs_review"] is True  # ainda faltam event, market e odd


def test_admin_can_force_needs_review(client, bankroll, use_extractor) -> None:
    """O recálculo é a regra, mas o admin pode segurar a tip na fila mesmo assim."""
    use_extractor(COMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]

    body = client.patch(
        f"/tips/{tip_id}", json={"stake_units": "2", "needs_review": True}
    ).json()

    assert body["needs_review"] is True


def test_patch_rejects_negative_units(client, bankroll, use_extractor) -> None:
    use_extractor(COMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]

    assert client.patch(f"/tips/{tip_id}", json={"stake_units": "-1"}).status_code == 422


# --- POST /tips/{id}/publish --------------------------------------------------


def test_publishes_with_the_stake_in_units(client, bankroll, use_extractor, use_senders) -> None:
    use_extractor(COMPLETE)
    telegram = FakeSender(Channel.TELEGRAM)
    use_senders(telegram)
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    response = client.post(f"/tips/{tip_id}/publish")

    assert response.status_code == 200
    body = response.json()
    assert body["channels"] == {"telegram": "sent"}
    assert "Stake: 2u" in body["message"]
    assert "R$" not in body["message"]
    assert telegram.sent == [body["message"]]


def test_publishing_records_the_message_log(client, bankroll, use_extractor, use_senders) -> None:
    use_extractor(COMPLETE)
    use_senders(FakeSender(Channel.TELEGRAM))
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    client.post(f"/tips/{tip_id}/publish")
    logs = client.get(f"/tips/{tip_id}").json()["messages"]

    assert len(logs) == 1
    assert logs[0]["channel"] == Channel.TELEGRAM.value
    assert logs[0]["status"] == MessageStatus.SENT.value
    assert logs[0]["sent_at"] is not None


def test_a_failing_channel_is_logged_not_raised(
    client,
    bankroll,
    use_extractor,
    use_senders,
) -> None:
    use_extractor(COMPLETE)
    use_senders(
        FakeSender(Channel.TELEGRAM, fail="chat not found"),
        FakeSender(Channel.WHATSAPP),
    )
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    body = client.post(f"/tips/{tip_id}/publish").json()

    assert body["channels"] == {"telegram": "failed", "whatsapp": "sent"}
    logs = {m["channel"]: m for m in client.get(f"/tips/{tip_id}").json()["messages"]}
    assert logs["telegram"]["error"] == "chat not found"


def test_refuses_to_publish_without_the_units(client, bankroll, use_extractor, use_senders) -> None:
    use_extractor(COMPLETE)
    use_senders(FakeSender(Channel.TELEGRAM))
    tip_id = create_tip(client, bankroll).json()["id"]

    response = client.post(f"/tips/{tip_id}/publish")

    assert response.status_code == 409
    # a mensagem chega ao admin: fala "unidades", não o nome da coluna
    detail = response.json()["detail"]
    assert "unidades" in detail
    assert "stake_units" not in detail


def test_refuses_to_publish_a_tip_that_was_not_read(
    client,
    bankroll,
    use_extractor,
    use_senders,
) -> None:
    use_extractor(INCOMPLETE)
    use_senders(FakeSender(Channel.TELEGRAM))
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    detail = client.post(f"/tips/{tip_id}/publish").json()["detail"]

    assert "evento" in detail and "mercado" in detail and "odd" in detail
    assert "stake_units" not in detail


def test_does_not_publish_the_same_tip_twice(client, bankroll, use_extractor, use_senders) -> None:
    """Sem isso um duplo clique no painel manda a mesma tip duas vezes no grupo."""
    use_extractor(COMPLETE)
    telegram = FakeSender(Channel.TELEGRAM)
    use_senders(telegram)
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    assert client.post(f"/tips/{tip_id}/publish").status_code == 200
    response = client.post(f"/tips/{tip_id}/publish")

    assert response.status_code == 409
    assert "force" in response.json()["detail"]
    assert len(telegram.sent) == 1


def test_force_republishes(client, bankroll, use_extractor, use_senders) -> None:
    use_extractor(COMPLETE)
    telegram = FakeSender(Channel.TELEGRAM)
    use_senders(telegram)
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)
    client.post(f"/tips/{tip_id}/publish")

    response = client.post(f"/tips/{tip_id}/publish", json={"force": True})

    assert response.status_code == 200
    assert len(telegram.sent) == 2


def test_publishing_without_any_channel_configured_is_a_conflict(
    client, bankroll, use_extractor, use_senders
) -> None:
    """Sem credencial o factory devolve lista vazia — melhor 409 que sucesso mudo."""
    use_extractor(COMPLETE)
    use_senders()
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    response = client.post(f"/tips/{tip_id}/publish")

    assert response.status_code == 409
    assert "canal" in response.json()["detail"].lower()


def test_publishing_an_unknown_tip_is_404(client) -> None:
    assert client.post("/tips/999/publish").status_code == 404


# --- DELETE /tips/{id} --------------------------------------------------------


def test_discards_a_tip_in_review(client, bankroll, use_extractor) -> None:
    use_extractor(COMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]

    response = client.delete(f"/tips/{tip_id}")

    assert response.status_code == 204
    assert client.get(f"/tips/{tip_id}").status_code == 404
    assert client.get(f"/bankrolls/{bankroll.id}/tips").json() == []


def test_discarding_a_published_tip_is_a_conflict(client, bankroll, use_extractor, use_senders
) -> None:
    """A mensagem já está no grupo; apagar o registro só esconderia o histórico."""
    use_extractor(COMPLETE)
    use_senders(FakeSender(Channel.TELEGRAM))
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)
    client.post(f"/tips/{tip_id}/publish")

    response = client.delete(f"/tips/{tip_id}")

    assert response.status_code == 409
    assert client.get(f"/tips/{tip_id}").status_code == 200


def test_discards_a_tip_whose_send_only_failed(
    client,
    bankroll,
    use_extractor,
    use_senders,
) -> None:
    """Tentativa que falhou não é publicação — a tip ainda pode ser descartada."""
    use_extractor(COMPLETE)
    use_senders(FakeSender(Channel.TELEGRAM, fail="canal fora do ar"))
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)
    client.post(f"/tips/{tip_id}/publish")

    response = client.delete(f"/tips/{tip_id}")

    assert response.status_code == 204
    assert client.get(f"/tips/{tip_id}").status_code == 404


def test_discarding_an_unknown_tip_is_404(client) -> None:
    assert client.delete("/tips/999").status_code == 404


def test_publishing_sends_the_stored_print_to_the_channels(
    client, bankroll, use_extractor, use_senders
) -> None:
    """O print gravado no POST /tips vai junto com a mensagem."""
    use_extractor(COMPLETE)
    telegram = FakeSender(Channel.TELEGRAM)
    use_senders(telegram)
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    client.post(f"/tips/{tip_id}/publish")

    assert telegram.imagens == [PNG]


# --- publicar é o que coloca a tip na banca -----------------------------------


def test_publishing_stamps_published_at(client, bankroll, use_extractor, use_senders) -> None:
    """`published_at` é o que libera marcar green/red e faz a tip entrar na banca."""
    use_extractor(COMPLETE)
    use_senders(FakeSender(Channel.TELEGRAM))
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    assert client.get(f"/tips/{tip_id}").json()["published_at"] is None

    client.post(f"/tips/{tip_id}/publish")

    assert client.get(f"/tips/{tip_id}").json()["published_at"] is not None


def test_publishing_that_failed_everywhere_does_not_stamp(
    client, bankroll, use_extractor, use_senders
) -> None:
    """Sem canal que aceite, a tip não chegou ao grupo — e não entra na banca."""
    use_extractor(COMPLETE)
    use_senders(FakeSender(Channel.TELEGRAM, fail="canal fora do ar"))
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    client.post(f"/tips/{tip_id}/publish")

    body = client.get(f"/tips/{tip_id}").json()
    assert body["published_at"] is None
    assert client.get(f"/bankrolls/{bankroll.id}/stats").json()["bets"] == 0


def test_republishing_keeps_the_first_publication_date(
    client, bankroll, use_extractor, use_senders
) -> None:
    """Reenviar não reescreve a entrada da tip na banca."""
    use_extractor(COMPLETE)
    use_senders(FakeSender(Channel.TELEGRAM))
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    client.post(f"/tips/{tip_id}/publish")
    primeira = client.get(f"/tips/{tip_id}").json()["published_at"]

    client.post(f"/tips/{tip_id}/publish", json={"force": True})

    assert client.get(f"/tips/{tip_id}").json()["published_at"] == primeira


def test_published_tip_can_be_marked(client, bankroll, use_extractor, use_senders) -> None:
    """O caminho feliz inteiro: print -> revisão -> publicar -> marcar green."""
    use_extractor(COMPLETE)
    use_senders(FakeSender(Channel.TELEGRAM))
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)
    client.post(f"/tips/{tip_id}/publish")

    response = client.post(f"/tips/{tip_id}/result", json={"status": "green"})

    assert response.status_code == 200
    assert response.json()["status"] == "green"
    assert client.get(f"/bankrolls/{bankroll.id}/stats").json()["green"] == 1


# --- link da aposta ---------------------------------------------------------


def test_link_goes_into_the_group_message(client, bankroll, use_extractor, use_senders) -> None:
    """O assinante abre a mesma aposta em vez de remontá-la campo a campo."""
    use_extractor(COMPLETE)
    sender = FakeSender(Channel.TELEGRAM)
    use_senders(sender)
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)
    client.patch(f"/tips/{tip_id}", json={"link": "https://bet365.com/bilhete/abc"})

    client.post(f"/tips/{tip_id}/publish")

    assert "https://bet365.com/bilhete/abc" in sender.sent[0]


def test_tip_without_link_still_publishes(client, bankroll, use_extractor, use_senders) -> None:
    """O link é opcional: sem ele a mensagem sai igual, só sem o atalho."""
    use_extractor(COMPLETE)
    sender = FakeSender(Channel.TELEGRAM)
    use_senders(sender)
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)

    response = client.post(f"/tips/{tip_id}/publish")

    assert response.status_code == 200
    assert "Entrar na aposta" not in sender.sent[0]


def test_link_without_scheme_is_refused(client, bankroll, use_extractor) -> None:
    """"bet365.com/abc" vira texto morto no Telegram — o assinante só descobre clicando."""
    use_extractor(COMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]

    response = client.patch(f"/tips/{tip_id}", json={"link": "bet365.com/abc"})

    assert response.status_code == 422


def test_empty_link_clears_the_field(client, bankroll, use_extractor) -> None:
    use_extractor(COMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]
    client.patch(f"/tips/{tip_id}", json={"link": "https://bet365.com/x"})

    body = client.patch(f"/tips/{tip_id}", json={"link": ""}).json()

    assert body["link"] is None


def test_refuses_to_publish_without_the_bet_amount(
    client, bankroll, use_extractor, use_senders
) -> None:
    """O valor em reais ancora as unidades — sem ele o encerramento não tem conta."""
    use_extractor(COMPLETE)
    use_senders(FakeSender(Channel.TELEGRAM))
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)
    client.patch(f"/tips/{tip_id}", json={"stake": None})

    response = client.post(f"/tips/{tip_id}/publish")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "valor da aposta" in detail
    assert "stake" not in detail.replace("valor da aposta", "")


def test_erasing_the_bet_amount_sends_the_tip_back_to_review(
    client, bankroll, use_extractor
) -> None:
    use_extractor(COMPLETE)
    tip_id = create_tip(client, bankroll).json()["id"]
    make_publishable(client, tip_id)
    assert client.get(f"/tips/{tip_id}").json()["needs_review"] is False

    body = client.patch(f"/tips/{tip_id}", json={"stake": None}).json()

    assert body["needs_review"] is True
