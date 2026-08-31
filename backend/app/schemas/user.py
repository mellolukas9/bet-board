"""Schemas da conta e da banca."""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.models.user import Bankroll


class BankrollRead(BaseModel):
    """Uma banca, como o dono dela vê no painel.

    O token do bot **nunca** sai inteiro daqui: o painel só precisa saber se
    está configurado e mostrar o fim dele para a pessoa se reconhecer. Ver
    ``telegram_bot_token_hint``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    is_public: bool
    created_at: datetime

    telegram_configured: bool
    telegram_bot_token_hint: str | None = None
    telegram_chat_id: str | None = None
    whatsapp_webhook_url: str | None = None


def bankroll_to_read(bankroll: "Bankroll") -> BankrollRead:
    """Serializa a banca **sem** o token do bot.

    O token dá poder de publicar no canal do cliente; ele entra no sistema uma
    vez e não sai mais. O que volta é uma pista — id do bot e os últimos
    dígitos — só para a pessoa reconhecer qual bot está ali.
    """
    return BankrollRead(
        id=bankroll.id,
        name=bankroll.name,
        slug=bankroll.slug,
        description=bankroll.description,
        is_public=bankroll.is_public,
        created_at=bankroll.created_at,
        telegram_configured=bankroll.telegram_configured,
        telegram_bot_token_hint=mask_token(bankroll.telegram_bot_token),
        telegram_chat_id=bankroll.telegram_chat_id,
        whatsapp_webhook_url=bankroll.whatsapp_webhook_url,
    )


def mask_token(token: str | None) -> str | None:
    """``1234567890:AAH…xYz9`` — id do bot é público, o segredo fica escondido."""
    if not token:
        return None

    bot_id, _, segredo = token.partition(":")
    if not segredo:
        return "…" + token[-4:]
    return f"{bot_id}:…{segredo[-4:]}"


class BankrollCreate(BaseModel):
    #: O endereço público sai daqui — não há campo de slug, de propósito.
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    is_public: bool = False


class BankrollUpdate(BaseModel):
    """Só os campos enviados mudam.

    Não há ``slug``: o endereço público é derivado do ``name`` e acompanha ele.
    Mandar os dois abriria a porta para `/b/vip-pecanha` numa banca chamada
    "Free" — que é justamente o que a regra evita.

    ``telegram_bot_token`` com string vazia **apaga** o token — é como o painel
    desconecta o canal.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    is_public: bool | None = None

    telegram_bot_token: str | None = Field(default=None, max_length=255)
    telegram_chat_id: str | None = Field(default=None, max_length=64)
    whatsapp_webhook_url: str | None = Field(default=None, max_length=512)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str | None
    is_active: bool
    is_superuser: bool
    created_at: datetime


class MeRead(BaseModel):
    """O que o painel carrega ao abrir: quem sou eu e quais bancas administro."""

    user: UserRead
    bankrolls: list[BankrollRead]


# --- assistente de configuração do Telegram -----------------------------------


class TelegramCheck(BaseModel):
    """Corpo do teste de conexão: confere o que ainda não foi salvo."""

    bot_token: str | None = Field(
        default=None,
        max_length=255,
        description="Token a testar. Sem isto, testa o que já está salvo na banca.",
    )
    chat_id: str | None = Field(default=None, max_length=64)


class TelegramDiagnostico(BaseModel):
    """Resultado do teste, em linguagem de gente."""

    ok: bool
    token_valido: bool
    bot_username: str | None
    bot_name: str | None
    canal_encontrado: bool
    canal_titulo: str | None
    canal_tipo: str | None
    bot_e_admin: bool
    pode_publicar: bool
    problemas: list[str]


class ChatDetectado(BaseModel):
    chat_id: str
    title: str
    type: str


class ChatsDetectados(BaseModel):
    chats: list[ChatDetectado]
    #: instrução para quando a lista vem vazia — é o caso mais comum na 1ª vez
    dica: str | None = None


# --- administração do sistema -------------------------------------------------


class AdminUserRead(UserRead):
    """Uma conta, como o administrador do sistema a vê."""

    last_login_at: datetime | None
    bankrolls: int
    tips: int


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=8, max_length=256)
    name: str | None = Field(default=None, max_length=120)
    #: Cria também a primeira banca do cliente, para ele já entrar com algo.
    bankroll_name: str | None = Field(default=None, max_length=120)
    is_superuser: bool = False


class AdminUserUpdate(BaseModel):
    """Ativar/desativar, renomear, promover ou trocar a senha de uma conta."""

    name: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
    is_superuser: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=256)
