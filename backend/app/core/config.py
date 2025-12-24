from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> Path | None:
    """
    Find .env file in deployment directory.

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

    # Redis settings (optional - not currently used)
    REDIS_URL: str | None = None
    REDIS_PASSWORD: str | None = None

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

    # LeanCloud settings (only sensitive master key in env)
    LEANCLOUD_MASTER_KEY: str

    # WeChat Mini Program settings
    WECHAT_APP_ID: str
    WECHAT_APP_SECRET: str

    # Snowflake ID settings
    SNOWFLAKE_DATACENTER_ID: int
    SNOWFLAKE_MACHINE_ID: int

    # Admin settings
    ADMIN_SECRET_KEY: str  # For session middleware

    # Aliyun Captcha credentials (server-side verification)

    CAPTCHA_CLIENT_WHITELIST: list[str] = Field(default_factory=lambda: ["wxminipg"])

    # Storage settings
    STORAGE_PUBLIC_DOMAIN: str = ""
    TENCENT_COS_SECRET_ID: str = ""
    TENCENT_COS_SECRET_KEY: str = ""
    TENCENT_COS_REGION: str = "ap-beijing"
    TENCENT_COS_BUCKET: str = ""
    TENCENT_COS_ENDPOINT: str = "https://cos.ap-beijing.myqcloud.com"

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
        """Check if running in development environment"""
        return self.ENVIRONMENT.lower() in ("development", "dev")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() in ("production", "prod")

    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment"""
        return self.ENVIRONMENT.lower() in ("staging", "test")

    @field_validator("CAPTCHA_CLIENT_WHITELIST", mode="before")
    @classmethod
    def _split_client_whitelist(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",")]
            return [item for item in parts if item]
        return value


@lru_cache
def get_settings() -> Settings:
    """
    Return cached Settings instance.

    Pydantic BaseSettings automatically loads values from environment variables
    and .env file as configured in model_config.
    """
    return Settings()


def reset_settings_cache() -> None:
    """Clear cached Settings instance."""

    get_settings.cache_clear()


__all__ = ["Settings", "get_settings", "reset_settings_cache"]
