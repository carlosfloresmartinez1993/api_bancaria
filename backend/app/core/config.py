from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (o del archivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "API Bancaria"
    ENVIRONMENT: Literal["development", "production", "test"] = "development"

    # Base de datos (PostgreSQL con driver psycopg 3)
    DATABASE_URL: str = Field(examples=["postgresql+psycopg://usuario:password@localhost:5432/banco"])

    @field_validator("DATABASE_URL")
    @classmethod
    def _driver_psycopg(cls, valor: str) -> str:
        # Render, Heroku y otros entregan postgres:// o postgresql://; SQLAlchemy necesita el driver.
        for prefijo in ("postgres://", "postgresql://"):
            if valor.startswith(prefijo):
                return "postgresql+psycopg://" + valor[len(prefijo):]
        return valor

    # Seguridad
    SECRET_KEY: str = Field(min_length=32, description="Clave para firmar los JWT; generar con `openssl rand -hex 32`")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=5, le=24 * 60)
    CORS_ORIGINS: list[str] = []
    LOGIN_RATE_LIMIT: str = "5/minute"
    RATE_LIMIT_ENABLED: bool = True
    DOCS_ENABLED: bool = True

    # Zona horaria del negocio: define qué es "hoy" y a qué hora corre el cierre
    TIMEZONE: str = "America/Tijuana"

    # Build del frontend (frontend/dist) que sirve app.servidor en producción
    FRONTEND_DIR: Path = Path("./static")

    # Correo (cierre diario)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    SMTP_SECURITY: Literal["starttls", "ssl", "none"] = "starttls"

    # Cierre diario automático
    SCHEDULER_ENABLED: bool = False
    CIERRE_HORA: int = Field(default=23, ge=0, le=23)
    CIERRE_MINUTO: int = Field(default=59, ge=0, le=59)
    CIERRE_ADJUNTAR_PDF: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
