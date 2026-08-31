"""Consolidação da banca — o que o painel mostra em cima da lista de tips."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import OwnedBankroll
from app.db.session import get_db
from app.schemas.stats import BankrollStats
from app.services import stats as stats_service

router = APIRouter(prefix="/bankrolls/{bankroll_id}/stats", tags=["stats"])


@router.get("", response_model=BankrollStats, summary="Números e curva da banca")
def bankroll(
    bankroll: OwnedBankroll,
    session: Annotated[Session, Depends(get_db)],
    since: Annotated[date | None, Query(description="Data inicial, inclusive")] = None,
    until: Annotated[date | None, Query(description="Data final, inclusive")] = None,
) -> BankrollStats:
    """Cartões (apostas, lucro, ROI, acerto) e a série diária do gráfico."""
    return BankrollStats(
        **stats_service.bankroll_summary(
            session, bankroll_id=bankroll.id, since=since, until=until
        )
    )
