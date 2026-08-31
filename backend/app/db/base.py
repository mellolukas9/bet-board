"""Base declarativa do SQLAlchemy.

Todos os models devem herdar de ``Base`` e ser importados em ``app.models``
para que o Alembic os enxergue no autogenerate.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Coluna ``created_at`` preenchida pelo banco."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
