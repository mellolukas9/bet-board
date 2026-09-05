"""O fuso do board: São Paulo.

Instante gravado continua sendo UTC — as colunas são ``timestamptz`` e o
servidor de produção roda em UTC. O fuso só entra na hora de responder "que
dia é esse?" e "que horas isso foi?": uma tip publicada às 22h de São Paulo é
01h do dia seguinte em UTC, e sem converter ela aparece na data errada para o
assinante e cai fora do filtro do dia.
"""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

#: Onde o grupo aposta. Todo dia/hora mostrado ou filtrado é lido daqui.
FUSO = ZoneInfo("America/Sao_Paulo")


def dia_local(momento: datetime) -> date:
    """O dia em São Paulo de um instante gravado."""
    return _com_fuso(momento).astimezone(FUSO).date()


def inicio_do_dia(dia: date) -> datetime:
    """00:00 de São Paulo, em UTC — a borda inicial de um filtro por data."""
    return _em_utc(datetime.combine(dia, time.min, tzinfo=FUSO))


def fim_do_dia(dia: date) -> datetime:
    """23:59:59.999999 de São Paulo, em UTC — a borda final, inclusive."""
    return _em_utc(datetime.combine(dia, time.max, tzinfo=FUSO))


def _em_utc(momento: datetime) -> datetime:
    """A borda vai para o banco já em UTC.

    O Postgres converteria sozinho (a coluna é ``timestamptz``), mas o SQLite
    dos testes grava o relógio de parede e joga o fuso fora — comparar em UTC
    dos dois lados é o que faz a borda valer nos dois bancos.
    """
    return momento.astimezone(UTC)


def _com_fuso(momento: datetime) -> datetime:
    """Datetime sem fuso é UTC: é o que o SQLite dos testes devolve."""
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=UTC)
