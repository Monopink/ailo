import os
from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path | None:
    """Find .env file in deployment directory.

    Searches from current file location upward to find project root,
    then looks for deployment/.env file.

    Returns:
        Path to .env file if found, None otherwise

    """
    current = Path(__file__).resolve()

    # Traverse up to find project root (contains deployment/)
    for parent in [current.parent.parent.parent, *current.parents]:
        env_file = parent / "deployment" / ".env"
        if env_file.exists():
            return env_file

    return None


class Settings(BaseSettings):
    """Application settings loaded from environment and .env files."""

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application settings
    APP_NAME: str
    VERSION: str
    DEBUG: bool = False
    ENVIRONMENT: str

    # Database settings
    DB_HOST: str
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    POSTGRES_ECHO: bool = False

    # Logging settings
    LOG_LEVEL: str
    LOG_FORMAT: str
    LOG_DIR: str

    # JWT settings
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Security settings
    BCRYPT_ROUNDS: int
    CORS_ORIGINS: list[str]
    ALLOWED_HOSTS: list[str]
    CLIENT_IP_MODE: Literal["peer", "trusted_header"] = "trusted_header"
    CLIENT_IP_HEADER: str = "X-Client-IP"
    TRUSTED_PROXY_CIDRS: list[str] = Field(default_factory=list)

    # LeanCloud settings (sensitive keys via env)
    LEANCLOUD_MASTER_KEY: str
    LEANCLOUD_IM_APP_ID: str
    LEANCLOUD_IM_APP_KEY: str

    # WeChat Mini Program settings
    WECHAT_APP_ID: str
    WECHAT_APP_SECRET: str

    # Snowflake ID settings
    SNOWFLAKE_DATACENTER_ID: int
    SNOWFLAKE_MACHINE_ID: int

    # Admin settings
    ADMIN_SECRET_KEY: str  # For session middleware
    ADMIN_TURNSTILE_SECRET_KEY: str | None = None
    ADMIN_TURNSTILE_SITE_KEY: str | None = None

    # Storage settings (media)
    TENCENT_COS_MEDIA_SECRET_ID: str
    TENCENT_COS_MEDIA_SECRET_KEY: str
    TENCENT_COS_MEDIA_REGION: str
    TENCENT_COS_MEDIA_BUCKET: str
    TENCENT_COS_MEDIA_ENDPOINT: str

    # Storage settings (backup - optional until used)
    TENCENT_COS_BACKUP_SECRET_ID: str | None = None
    TENCENT_COS_BACKUP_SECRET_KEY: str | None = None
    TENCENT_COS_BACKUP_REGION: str | None = None
    TENCENT_COS_BACKUP_BUCKET: str | None = None
    TENCENT_COS_BACKUP_ENDPOINT: str | None = None

    def get_env(self, key: str) -> str | None:
        """Read raw environment variable value by key."""
        return os.getenv(key)

    @property
    def database_url(self) -> str:
        """Constructs the PostgreSQL database URL from settings."""
        return (
            "postgresql+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/"
            f"{self.DB_NAME}"
        )

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() in ("development", "dev")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() in ("production", "prod")

    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.ENVIRONMENT.lower() in ("staging", "test")

    @field_validator("TRUSTED_PROXY_CIDRS", mode="before")
    @classmethod
    def _split_trusted_proxy_cidrs(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",")]
            return [item for item in parts if item]
        return value

    @field_validator("TRUSTED_PROXY_CIDRS")
    @classmethod
    def _validate_trusted_proxy_cidrs(cls, value: list[str]) -> list[str]:
        for item in value:
            if item == "*":
                raise ValueError("TRUSTED_PROXY_CIDRS cannot include wildcard '*'")
            ip_network(item, strict=False)
        return value

    @model_validator(mode="after")
    def _validate_client_ip_security(self) -> "Settings":
        if self.CLIENT_IP_MODE == "trusted_header" and not self.TRUSTED_PROXY_CIDRS:
            raise ValueError("TRUSTED_PROXY_CIDRS must be configured in trusted_header mode")
        return self

    @field_validator("CLIENT_IP_HEADER")
    @classmethod
    def _validate_client_ip_header(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("CLIENT_IP_HEADER must be configured")
        return normalized

    @field_validator(
        "ADMIN_TURNSTILE_SECRET_KEY",
        "ADMIN_TURNSTILE_SITE_KEY",
        mode="before",
    )
    @classmethod
    def _normalize_optional_turnstile_settings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator(
        "TENCENT_COS_MEDIA_SECRET_ID",
        "TENCENT_COS_MEDIA_SECRET_KEY",
        "TENCENT_COS_MEDIA_REGION",
        "TENCENT_COS_MEDIA_BUCKET",
        "TENCENT_COS_MEDIA_ENDPOINT",
        mode="before",
    )
    @classmethod
    def _validate_required_media_settings(cls, value: str | None, info: ValidationInfo) -> str:
        if value is None:
            raise ValueError(f"{info.field_name} must be configured")
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} must be configured")
        return normalized

    @field_validator(
        "TENCENT_COS_BACKUP_SECRET_ID",
        "TENCENT_COS_BACKUP_SECRET_KEY",
        "TENCENT_COS_BACKUP_REGION",
        "TENCENT_COS_BACKUP_BUCKET",
        "TENCENT_COS_BACKUP_ENDPOINT",
        mode="before",
    )
    @classmethod
    def _normalize_optional_backup_settings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance.

    Pydantic BaseSettings automatically loads values from environment variables
    and .env file as configured in model_config.
    """
    return Settings()


def reset_settings_cache() -> None:
    """Clear cached Settings instance."""
    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "reset_settings_cache"]
