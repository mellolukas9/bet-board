"""Configuração da aplicação, lida do ambiente (.env)."""

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- aplicação ---
    app_name: str = "Bet Board API"
    environment: Literal["local", "dev", "prod", "test"] = "local"
    debug: bool = False
    log_level: str = "INFO"

    # --- banco ---
    # 5433 é a porta que o Compose expõe no host (ver docker-compose.yml)
    database_url: str = "postgresql+psycopg://betboard:betboard@localhost:5433/betboard"
    db_connect_timeout: int = 5

    # --- CORS (origens do frontend) ---
    # NoDecode desliga o parse automático de JSON do pydantic-settings: sem ele
    # o valor do ambiente é decodificado antes do validador, e uma lista por
    # vírgula estoura com "Expecting value".
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _aceita_lista_por_virgula(cls, valor: object) -> object:
        """Aceita ``a,b`` além do JSON ``["a","b"]``.

        Painel de host gerenciado é um campo de texto: exigir JSON válido ali
        rende erro de aspas na madrugada do deploy.
        """
        if isinstance(valor, str):
            texto = valor.strip()
            if texto.startswith("["):
                return json.loads(texto)
            return [item.strip() for item in texto.split(",") if item.strip()]
        return valor

    @field_validator("database_url", mode="before")
    @classmethod
    def _normaliza_driver(cls, valor: object) -> object:
        """Força o driver psycopg na URL do banco.

        Neon, Render e afins entregam a string como ``postgres://`` ou
        ``postgresql://``, que o SQLAlchemy tenta abrir com psycopg2 — que não
        está instalado. Trocar o prefixo à mão é o erro de deploy mais fácil de
        cometer e o mais chato de diagnosticar, então é feito aqui.
        """
        if isinstance(valor, str):
            for prefixo in ("postgresql+psycopg://", "postgresql+psycopg2://"):
                if valor.startswith(prefixo):
                    return valor
            for prefixo in ("postgresql://", "postgres://"):
                if valor.startswith(prefixo):
                    return "postgresql+psycopg://" + valor[len(prefixo) :]
        return valor

    # --- integrações (usadas a partir da Fase 1) ---
    vision_provider: str = "gemini"
    vision_api_key: str = ""
    vision_model: str = "models/gemini-3.5-flash-lite"
    # 503/429 do provedor são picos de demanda, não print ruim: tenta de novo
    # antes de reprovar a tip. 1 tentativa = sem retry.
    vision_max_attempts: int = 3
    vision_retry_base_delay: float = 1.0
    # Teto por tentativa. Sem ele, uma chamada travada segura a requisição
    # indefinidamente — medimos 503 levando 60s para voltar, e o retry
    # multiplicava isso por 3. Chamada saudável responde em ~3s.
    vision_timeout_seconds: float = 30.0
    # Resolução com que o provedor processa a imagem. "low" gasta ~62% menos
    # tokens de entrada que o padrão e responde mais rápido, ao custo de
    # possível perda de acerto em letra miúda (odd, stake). "default" não manda
    # o parâmetro e deixa o provedor escolher.
    vision_media_resolution: Literal["default", "low", "medium", "high"] = "low"

    # --- sessão do painel ---
    # Chave que assina o JWT. Vazia = uma aleatória por processo, o que derruba
    # as sessões a cada restart — aceitável local, não em produção.
    auth_secret_key: str = ""
    # Teto absoluto da sessão: nem quem fica o dia inteiro no painel passa
    # disso sem digitar a senha de novo.
    auth_token_ttl_minutes: int = 60 * 12
    # Inatividade que derruba a sessão. É o `exp` de cada token: o painel o
    # renova enquanto a pessoa mexe na tela, e para de renovar quando ela para —
    # então o token morre sozinho no servidor, sem depender do navegador.
    auth_idle_timeout_minutes: int = 10

    # --- primeiro administrador (só para deploy remoto) ---
    # Preenchidas, a API cria (ou promove) esta conta no start. Existe porque
    # num host gerenciado nem sempre há shell para rodar a CLI — e sem uma
    # conta administradora o painel de administração nasce inacessível.
    # Idempotente: rodar de novo não duplica nem troca a senha de quem já existe.
    superuser_username: str = ""
    superuser_password: str = ""

    # Os canais de envio (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    # WHATSAPP_WEBHOOK_URL) e o usuário do painel **não** moram mais aqui: são
    # por banca, no banco, e o cliente os configura pelo próprio painel. Um
    # servidor atende vários tipsters, cada um com o seu grupo.
    #
    # Quem tinha esses valores no .env não os perdeu: a migration
    # `c3a1d5e7f204` leu o ambiente uma última vez e os moveu para a primeira
    # banca. Contas novas nascem por `python -m app.cli create-user`.


@lru_cache
def get_settings() -> Settings:
    """Settings em cache — uma única instância por processo."""
    return Settings()
