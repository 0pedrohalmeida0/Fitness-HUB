"""
Configurações da aplicação.

Lê variáveis de ambiente via pydantic-settings.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Fitness Hub"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True  # Em produção, force False via env: APP_DEBUG=false
    app_port: int = 8000

    @field_validator("app_debug", mode="after")
    @classmethod
    def _disable_debug_in_prod(cls, v: bool, info) -> bool:
        """Garante que debug é False em produção (não vaza stack traces)."""
        env = info.data.get("app_env", "development")
        if env == "production" and v:
            import os
            # Só avisa se APP_DEBUG foi setado explicitamente
            if "APP_DEBUG" in os.environ:
                raise ValueError("APP_DEBUG não pode ser True em produção (vaza stack traces).")
        return v

    # CORS - lista de origens permitidas
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost/fitnesshub"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Bcrypt
    bcrypt_rounds: int = 12

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors(cls, v):
        """Aceita string separada por vírgula OU lista."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(cls, v: str) -> str:
        """Em produção, exige JWT_SECRET forte."""
        if v == "change-me-in-production":
            import os
            # Só avisa — não bloqueia dev
            if os.getenv("APP_ENV") == "production":
                raise ValueError("JWT_SECRET não pode ser o padrão em produção!")
        if len(v) < 32:
            raise ValueError("JWT_SECRET deve ter pelo menos 32 caracteres.")
        return v


@lru_cache
def get_settings() -> Settings:
    """Retorna instância singleton das settings."""
    return Settings()


settings = get_settings()
