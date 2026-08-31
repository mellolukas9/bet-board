"""Engine e sessão do SQLAlchemy."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_settings = get_settings()

# connect_timeout evita que a API (e os testes) fiquem pendurados quando o
# Postgres não está de pé — o /health prefere reportar "down" rápido. É opção do
# psycopg: em SQLite (usado para rodar a API sem Docker) o driver recusaria o
# argumento e nem subiria.
_connect_args = (
    {"connect_timeout": _settings.db_connect_timeout}
    if _settings.database_url.startswith("postgresql")
    else {}
)

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    echo=_settings.debug,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependência do FastAPI: uma sessão por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
