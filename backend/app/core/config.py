from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application settings
    PROJECT_NAME: str
    VERSION: str
    DEBUG: bool
    ENVIRONMENT: str

    # Database settings
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DATABASE: str
    POSTGRES_ECHO: bool

    # Redis settings
    REDIS_URL: str
    REDIS_PASSWORD: Optional[str] = None

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
    CORS_ORIGINS: List[str]
    ALLOWED_HOSTS: List[str]

    # LeanCloud settings (only sensitive master key in env)
    LEANCLOUD_MASTER_KEY: str

    # Snowflake ID settings
    SNOWFLAKE_DATACENTER_ID: int
    SNOWFLAKE_MACHINE_ID: int

    # Admin settings
    ADMIN_SECRET_KEY: str  # For session middleware

    @property
    def database_url(self) -> str:
        """Constructs the PostgreSQL database URL from settings."""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT.lower() in ("development", "dev")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() in ("production", "prod")


settings = Settings()
