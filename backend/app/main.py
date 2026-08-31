"""Entrypoint da API FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, auth, bankrolls, health, public, stats, tips
from app.config import get_settings
from app.core.logging import get_logger, setup_logging

settings = get_settings()
logger = get_logger(__name__)


def _bootstrap_superuser() -> None:
    """Cria o primeiro administrador a partir do ambiente, se pedido.

    Falha de banco aqui **não** impede a API de subir: o ``/health`` já reporta
    o banco em separado, e derrubar a aplicação inteira por causa disso só
    tornaria o problema mais difícil de enxergar.
    """
    if not (settings.superuser_username and settings.superuser_password):
        return

    # imports tardios: só este caminho precisa do banco carregado
    from app.db.session import SessionLocal
    from app.services import users as users_service

    try:
        with SessionLocal() as session:
            users_service.ensure_superuser(
                session,
                username=settings.superuser_username,
                password=settings.superuser_password,
            )
            session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("app.superuser_bootstrap_failed", extra={"error": str(exc)})


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    logger.info("app.startup", extra={"environment": settings.environment})
    _bootstrap_superuser()
    yield
    logger.info("app.shutdown")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(public.router)
app.include_router(bankrolls.router)
app.include_router(stats.router)
app.include_router(tips.nested_router)
app.include_router(tips.router)
