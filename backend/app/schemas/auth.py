"""Schemas do login do admin."""

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    """Sessão emitida pelo login."""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    username: str


class AdminRead(BaseModel):
    """Quem está logado (``GET /auth/me``)."""

    username: str
