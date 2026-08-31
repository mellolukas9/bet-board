"""Página pública da banca.

A única rota sem login além do ``/health``. É o endereço que o tipster manda
para os assinantes do grupo: `/b/<slug>`.

Duas travas valem a leitura:

1. **Banca privada responde 404**, não 403 — quem não pode ver não precisa
   saber que ela existe.
2. **Nada em reais sai daqui.** Os schemas de ``app.schemas.public`` são outros,
   não um recorte dos internos: um campo novo em ``TipRead`` não vaza para cá
   por descuido, porque precisaria ser escrito nos dois lugares.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db
from app.models.user import Bankroll
from app.schemas.public import PublicBankroll, PublicPoint, PublicStats, PublicTip
from app.services import bankrolls as bankrolls_service
from app.services import stats as stats_service
from app.services import tips as tips_service

logger = get_logger(__name__)

router = APIRouter(prefix="/public", tags=["public"])

#: Teto de apostas listadas. A página é prova de performance, não um dump.
MAX_TIPS = 200


@router.get(
    "/bankrolls/{slug}",
    response_model=PublicBankroll,
    summary="Resultados públicos de uma banca (sem login)",
)
def public_bankroll(
    slug: Annotated[str, Path(max_length=64)],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=MAX_TIPS)] = 100,
) -> PublicBankroll:
    bankroll = bankrolls_service.get_by_slug(session, slug)

    if bankroll is None or not bankroll.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Banca não encontrada ou não publicada.",
        )

    resumo = stats_service.bankroll_summary(session, bankroll_id=bankroll.id)
    tips = tips_service.list_tips(session, bankroll_id=bankroll.id, limit=limit)

    logger.info("public.viewed", extra={"bankroll_id": bankroll.id, "slug": bankroll.slug})

    return PublicBankroll(
        name=bankroll.name,
        slug=bankroll.slug,
        description=bankroll.description,
        owner_name=bankroll.owner.name,
        since=_primeira_aposta(bankroll),
        stats=_public_stats(resumo),
        tips=[PublicTip.model_validate(t) for t in tips],
    )


def _public_stats(resumo: dict) -> PublicStats:
    """Recorta o consolidado interno, deixando os valores em reais de fora."""
    return PublicStats(
        bets=resumo["bets"],
        settled=resumo["settled"],
        pending=resumo["pending"],
        green=resumo["green"],
        red=resumo["red"],
        void=resumo["void"],
        staked_units=resumo["staked_units"],
        profit_units=resumo["profit_units"],
        roi=resumo["roi"],
        hit_rate=resumo["hit_rate"],
        series=[
            PublicPoint(
                date=p["date"],
                bets=p["bets"],
                profit_units=p["profit_units"],
                cumulative_units=p["cumulative_units"],
            )
            for p in resumo["series"]
        ],
    )


def _primeira_aposta(bankroll: Bankroll):
    """Desde quando a banca tem histórico — o "operando desde" da página."""
    return bankroll.tips[0].created_at if bankroll.tips else None
