"""Ciclo de vida da tip (Fase 1.5).

Amarra o que já existia solto: extração (1.2), formatação (1.3) e despacho
(1.4). A regra de negócio mora aqui, não nas rotas — a rota só traduz para HTTP.

Publicar é um passo separado de criar, por decisão de projeto: o grupo aposta em
unidades ("2u") e o print só mostra reais, então a tip espera o admin informar
``stake_units`` na revisão antes de virar mensagem.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.logging import get_logger
from app.core.tz import fim_do_dia, inicio_do_dia
from app.models.tip import MessageLog, MessageStatus, Tip, TipStatus
from app.models.user import Bankroll
from app.schemas.tip import TipExtracted, TipUpdate
from app.services.messaging import dispatch_tip_message, format_tip_message
from app.services.messaging.base import MessageSender
from app.services.vision.base import VisionError, VisionExtractor

logger = get_logger(__name__)

#: Sem estes campos a mensagem sai capenga — a tip fica na fila de revisão.
#: ``stake_units`` entra na lista porque só o admin sabe convertê-lo.
#:
#: ``stake`` (o valor em reais) entra porque é ele que ancora as unidades: o
#: encerramento antecipado é informado em reais e vira unidades pela proporção
#: com o stake. Sem ele, uma tip encerrada não tem como entrar na banca.
REQUIRED_TO_PUBLISH: tuple[str, ...] = (
    "event",
    "market",
    "odd",
    "stake",
    "stake_units",
)

#: Nome de coluna não é nome de campo na tela. O admin lê "unidades", não
#: "stake_units" — e essa mensagem chega até ele, no 409 do publish.
ROTULOS: dict[str, str] = {
    "event": "evento",
    "market": "mercado",
    "odd": "odd",
    "stake": "valor da aposta",
    "stake_units": "unidades",
}


class TipNotPublishable(RuntimeError):
    """A tip ainda não tem o que a mensagem precisa, ou já foi publicada."""


class TipNotDiscardable(RuntimeError):
    """A tip já foi para o grupo — descartar não desfaz isso."""


class TipNotResolvable(RuntimeError):
    """A tip ainda não foi publicada; não há resultado a marcar."""


class TipNotCashable(RuntimeError):
    """Falta o que a conta do encerramento precisa (o stake da tip)."""


def create_tip_from_image(
    session: Session,
    *,
    bankroll: Bankroll,
    image: bytes,
    media_type: str,
    extractor: VisionExtractor,
    raw_image_ref: str | None = None,
) -> Tip:
    """Lê o print e grava a tip, mesmo quando a leitura falha.

    Falha do provedor **não** vira erro para o cliente: a tip é persistida com
    ``extraction_error`` e ``needs_review``, para o admin completar à mão em vez
    de ter que reenviar o print.
    """
    extracted: TipExtracted | None = None
    error: str | None = None

    try:
        extracted = extractor.extract(image, media_type)
    except VisionError as exc:
        error = str(exc)
        logger.warning("tips.create.vision_error", extra={"error": error})

    tip = Tip(
        bankroll_id=bankroll.id,
        status=TipStatus.PENDING,
        raw_image_ref=raw_image_ref,
        raw_image=image,
        raw_image_media_type=media_type,
        currency="BRL",
    )

    if extracted is not None:
        tip.source = extracted.source
        tip.event = extracted.event
        tip.market = extracted.market
        tip.odd = _to_decimal(extracted.odd)
        tip.stake = _to_decimal(extracted.stake)
        tip.currency = (extracted.currency or "BRL").upper()[:3]
        tip.extraction_error = extracted.unreadable_reason
        tip.extracted_at = datetime.now(UTC)
    else:
        tip.extraction_error = error

    # stake_units nunca vem da IA, então toda tip nasce precisando de revisão.
    tip.needs_review = bool(missing_to_publish(tip))

    session.add(tip)
    session.flush()

    logger.info(
        "tips.created",
        extra={
            "tip_id": tip.id,
            "bankroll_id": bankroll.id,
            "needs_review": tip.needs_review,
            "missing": missing_to_publish(tip),
        },
    )
    return tip


def list_tips(
    session: Session,
    *,
    bankroll_id: int,
    status: TipStatus | None = None,
    needs_review: bool | None = None,
    published_only: bool = False,
    since: date | None = None,
    until: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Tip]:
    """Lista as tips **de uma banca**, mais recentes primeiro.

    ``published_only`` é o recorte da banca: só entra o que foi para o grupo.
    ``since``/``until`` recortam por ``created_at``, inclusive nas duas pontas,
    com o dia começando e terminando **em São Paulo** — o mesmo campo e o mesmo
    critério do ``/stats``, para lista e cartões falarem do mesmo período.
    """
    stmt = (
        select(Tip)
        .options(selectinload(Tip.messages))
        .where(Tip.bankroll_id == bankroll_id)
    )

    if published_only:
        stmt = stmt.where(Tip.published_at.is_not(None))
    if status is not None:
        stmt = stmt.where(Tip.status == status)
    if needs_review is not None:
        stmt = stmt.where(Tip.needs_review == needs_review)
    if since is not None:
        stmt = stmt.where(Tip.created_at >= inicio_do_dia(since))
    if until is not None:
        stmt = stmt.where(Tip.created_at <= fim_do_dia(until))

    stmt = stmt.order_by(Tip.id.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt))


def get_tip(session: Session, tip_id: int) -> Tip | None:
    """A tip com os envios e a banca dona — é ela que diz de quem é a tip."""
    stmt = (
        select(Tip)
        .options(selectinload(Tip.messages), joinedload(Tip.bankroll))
        .where(Tip.id == tip_id)
    )
    return session.scalars(stmt).one_or_none()


def update_tip(session: Session, tip: Tip, data: TipUpdate) -> Tip:
    """Aplica a correção manual do admin.

    Só os campos enviados mudam. ``needs_review`` é recalculado a partir do que
    a tip passou a ter — a menos que o admin diga explicitamente o contrário.
    """
    changes = data.model_dump(exclude_unset=True)
    explicit_review = changes.pop("needs_review", None)
    # O status tem regra própria (carimba resolved_at, grava result_raw); passar
    # por set_result evita uma tip "green" sem data de resolução.
    new_status = changes.pop("status", None)

    for field, value in changes.items():
        setattr(tip, field, value)

    if new_status is not None and TipStatus(new_status) is not tip.status:
        set_result(session, tip, TipStatus(new_status))

    if tip.currency:
        tip.currency = tip.currency.upper()[:3]

    _drop_stale_extraction_error(tip)

    # Corrigir a tip é justamente o que tira ela da fila; recalcular evita que
    # ela fique marcada para revisão para sempre depois de completada.
    tip.needs_review = (
        explicit_review if explicit_review is not None else bool(missing_to_publish(tip))
    )

    session.flush()
    logger.info(
        "tips.updated",
        extra={
            "tip_id": tip.id,
            "fields": sorted([*changes, *(["status"] if new_status is not None else [])]),
            "needs_review": tip.needs_review,
        },
    )
    return tip


def set_result(
    session: Session,
    tip: Tip,
    status: TipStatus,
    note: str | None = None,
    *,
    cashout_amount: Decimal | None = None,
) -> Tip:
    """Grava o resultado que o **admin** informou (green / red / void / cashout).

    Nesta fase não há API esportiva: quem confere o placar é o dono do grupo,
    pelo painel. Por isso o ``result_raw`` guarda ``source: "manual"`` — quando
    a validação automática da Fase 2 entrar, dá para separar o que foi conferido
    à mão do que veio de fora.

    ``cashout`` é o encerramento antecipado: a aposta saiu antes do fim do jogo,
    pelo valor que a casa ofereceu. Ele **pode dar lucro ou prejuízo** — o que
    define é a diferença para o stake, e não há green nem red a declarar.

    Voltar para ``pending`` desfaz o resultado (erro de clique acontece) e limpa
    o ``resolved_at`` — e, com ele, o valor do encerramento.

    Raises:
        TipNotResolvable: a tip ainda não foi publicada. Aposta que não chegou
            ao grupo não tem resultado a confirmar — e marcá-la mexeria no
            lucro da banca por algo que ninguém seguiu.
        TipNotCashable: encerramento sem valor informado, ou numa tip sem o
            stake em reais — é dele que sai a proporção em unidades.
    """
    if not was_published(tip):
        raise TipNotResolvable(
            "Esta tip ainda não foi publicada. Publique-a no grupo antes de "
            "marcar o resultado."
        )

    if status is TipStatus.CASHOUT:
        _check_cashout(tip, cashout_amount)

    tip.status = status
    # o valor só sobrevive no encerramento: marcar green depois de encerrar
    # deixaria para trás um número que não descreve mais o resultado
    tip.cashout_amount = cashout_amount if status is TipStatus.CASHOUT else None

    if status is TipStatus.PENDING:
        tip.resolved_at = None
        tip.result_raw = None
    else:
        tip.resolved_at = datetime.now(UTC)
        tip.result_raw = {
            "source": "manual",
            "status": status.value,
            "note": note,
            "at": tip.resolved_at.isoformat(),
        }
        if status is TipStatus.CASHOUT:
            tip.result_raw["cashout_amount"] = str(cashout_amount)

    session.flush()
    logger.info("tips.result_set", extra={"tip_id": tip.id, "status": status.value})
    return tip


def _check_cashout(tip: Tip, cashout_amount: Decimal | None) -> None:
    """O encerramento precisa do valor devolvido e do valor apostado.

    O painel converte um no outro pela proporção (ver ``Tip.cashout_units``);
    com stake zerado ou ausente a conta seria uma divisão por zero, e a tip
    entraria na banca valendo nada.
    """
    if cashout_amount is None:
        raise TipNotCashable(
            "Informe por quanto a aposta foi encerrada (o valor devolvido pela "
            "casa, em reais)."
        )
    if not tip.stake:
        raise TipNotCashable(
            "Esta tip não tem o valor da aposta em reais, e é dele que sai a "
            "proporção do encerramento. Preencha o valor da aposta antes."
        )
    if tip.stake_units is None:
        raise TipNotCashable(
            "Esta tip não tem as unidades informadas — sem elas o encerramento "
            "não entra na banca."
        )


def discard_tip(session: Session, tip: Tip) -> None:
    """Apaga uma tip que o admin decidiu não publicar.

    Só vale para tip que **nunca** foi enviada: uma vez no grupo, a mensagem
    existe fora do banco e sumir com o registro só esconderia o histórico.

    Raises:
        TipNotDiscardable: a tip já foi publicada em algum canal.
    """
    if was_published(tip):
        raise TipNotDiscardable(
            "Esta tip já foi publicada e não pode ser descartada."
        )

    tip_id = tip.id
    session.delete(tip)
    session.flush()
    logger.info("tips.discarded", extra={"tip_id": tip_id})


def missing_to_publish(tip: Tip) -> list[str]:
    """Campos que faltam para a tip virar mensagem."""
    return [f for f in REQUIRED_TO_PUBLISH if getattr(tip, f) is None]


def _drop_stale_extraction_error(tip: Tip) -> None:
    """Apaga o aviso de leitura quando ele não descreve mais a tip.

    ``extraction_error`` é o que a IA disse **do print** ("não achei o valor
    apostado", "parece cortado"). Uma vez que o admin preencheu o que faltava, o
    aviso passa a contradizer os campos logo abaixo dele — e, antes disto, ele
    sobrevivia à revisão e à publicação, deixando na tela uma falha já
    resolvida.

    O critério é o mesmo do publish: sem campo faltando, o que a IA não
    conseguiu ler alguém já leu por ela. Enquanto faltar algo, o aviso continua
    — ali ele ainda explica *por que* falta.
    """
    if tip.extraction_error and not missing_to_publish(tip):
        tip.extraction_error = None


def was_published(tip: Tip) -> bool:
    """True se a tip já foi entregue em algum canal."""
    return tip.published_at is not None


def publish_tip(
    session: Session,
    tip: Tip,
    *,
    senders: list[MessageSender],
    force: bool = False,
) -> tuple[str, list[MessageLog]]:
    """Formata a tip e despacha nos canais, registrando cada envio.

    Raises:
        TipNotPublishable: falta campo, ou a tip já foi publicada sem ``force``.
    """
    missing = missing_to_publish(tip)
    if missing:
        faltando = ", ".join(ROTULOS.get(campo, campo) for campo in missing)
        raise TipNotPublishable(
            f"A tip ainda não pode ser publicada. Falta preencher: {faltando}."
        )
    if was_published(tip) and not force:
        raise TipNotPublishable(
            "Esta tip já foi publicada. Use force=true para enviar de novo."
        )
    if not senders:
        raise TipNotPublishable(
            "Nenhum canal de envio configurado. Confira TELEGRAM_BOT_TOKEN e "
            "TELEGRAM_CHAT_ID no .env."
        )

    # A tip passou pelas checagens acima, então está completa: um aviso de
    # leitura que tenha sobrado de antes da revisão não descreve o que está indo
    # para o grupo agora. Tips publicadas antes desta regra são limpas aqui na
    # próxima vez que passarem por aqui.
    _drop_stale_extraction_error(tip)

    text = format_tip_message(
        _as_extracted(tip),
        # o evento vem da tip, não da leitura: é ele que o admin pode ter
        # corrigido na revisão
        event=tip.event,
        stake_units=tip.stake_units,
        link=tip.link,
    )
    logs = dispatch_tip_message(
        session,
        tip_id=tip.id,
        text=text,
        senders=senders,
        # tip anterior à coluna raw_image não tem print guardado; vai só o texto
        image=tip.raw_image,
        media_type=tip.raw_image_media_type,
    )

    # Só carimba se algum canal aceitou. Publicação que falhou em todos não
    # colocou a tip no grupo, e ela não pode entrar na banca por isso.
    if tip.published_at is None and any(log.status is MessageStatus.SENT for log in logs):
        tip.published_at = datetime.now(UTC)

    session.flush()
    logger.info(
        "tips.published",
        extra={
            "tip_id": tip.id,
            "channels": {log.channel.value: log.status.value for log in logs},
        },
    )
    return text, logs


def _as_extracted(tip: Tip) -> TipExtracted:
    """Adapta a tip do banco para o schema que o formatter consome."""
    return TipExtracted(
        source=tip.source,
        # `matches` só existe na leitura do print; o nome do evento já está
        # gravado na tip e vai para o formatter por fora
        matches=None,
        market=tip.market,
        odd=float(tip.odd) if tip.odd is not None else None,
        stake=float(tip.stake) if tip.stake is not None else None,
        currency=tip.currency,
        unreadable_reason=None,
    )


def _to_decimal(value: float | None) -> Decimal | None:
    """A IA devolve float; o banco guarda Numeric — o str evita 1.8500000000000001."""
    return None if value is None else Decimal(str(value))
