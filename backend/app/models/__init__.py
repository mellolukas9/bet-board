"""Models SQLAlchemy.

Importe aqui todos os models para que o ``Base.metadata`` fique completo e o
Alembic consiga fazer autogenerate.
"""

from app.db.base import Base
from app.models.tip import (
    Channel,
    MessageLog,
    MessageStatus,
    Tip,
    TipStatus,
)
from app.models.user import Bankroll, User

__all__ = [
    "Bankroll",
    "Base",
    "Channel",
    "MessageLog",
    "MessageStatus",
    "Tip",
    "TipStatus",
    "User",
]
