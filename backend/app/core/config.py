from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # Configuration is now purely environment variable driven
    # No env_file dependency - all variables must be provided via environment
    model_config = SettingsConfigDict(extra="ignore")

    PROJECT_NAME: str = "Backend"

    # Database settings
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # JWT settings - must be provided via environment variables
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # LeanCloud settings
    LEANCLOUD_APP_ID: str
    LEANCLOUD_APP_KEY: str
    LEANCLOUD_MASTER_KEY: str
    LEANCLOUD_SERVER_URL: Optional[str] = None
    LEANCLOUD_BASE_URL: str

    # LeanCloud Health Check settings
    LEANCLOUD_HEALTH_CHECK_INTERVAL: Optional[int] = None  # No default - must be configured
    LEANCLOUD_HEALTH_CHECK_TIMEOUT: Optional[int] = None  # No default - must be configured
    LEANCLOUD_RECOVERY_COOLDOWN_SECONDS: Optional[int] = None  # No default - must be configured

    # User contact limits
    DEFAULT_CONTACT_LIMIT: int = 1
    DEFAULT_SEARCH_DISPLAY_LIMIT: int = 2
    ADD_CONTACT_TIMEOUT: int = 300

    # Entity ID settings
    ENTITY_ID_PREFIX: str = "qqid_"

    # Database logging settings
    DB_ECHO: bool = False  # Set to True for SQL query logging in development

    @property
    def database_url(self) -> str:
        """
        Constructs the database URL from settings.
        """
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


# Create a single settings instance to be used across the application
settings = Settings()
