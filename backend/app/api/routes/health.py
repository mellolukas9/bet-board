"""Rota de health check."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Diz se a API está de pé e se o banco responde.

    Só a API precisa estar viva para responder 200 — o banco é reportado à parte
    para que o frontend consiga distinguir "backend fora" de "banco fora".
    """
    settings = get_settings()

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "up"
    except Exception:
        database = "down"

    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        database=database,
    )
