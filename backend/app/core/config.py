from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # Configuration is now purely environment variable driven
    # No env_file dependency - all variables must be provided via environment
    model_config = SettingsConfigDict(extra="ignore")

    PROJECT_NAME: str = "Says Chat Service"

    # LeanCloud settings
    LEANCLOUD_APP_ID: str
    LEANCLOUD_APP_KEY: str
    LEANCLOUD_MASTER_KEY: str
    LEANCLOUD_SERVER_URL: Optional[str] = None
    LEANCLOUD_BASE_URL: str

    # Database settings
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # Internal service authentication
    INTERNAL_SERVICE_KEY: str = "default_internal_key_change_me"

    # LeanCloud Health Check settings
    LEANCLOUD_HEALTH_CHECK_INTERVAL: Optional[int] = None  # No default - must be configured
    LEANCLOUD_HEALTH_CHECK_TIMEOUT: Optional[int] = None  # No default - must be configured
    LEANCLOUD_RECOVERY_COOLDOWN_SECONDS: Optional[int] = None  # No default - must be configured

    @property
    def database_url(self) -> str:
        """
        Constructs the database URL from settings.
        """
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


# Create a single settings instance to be used across the application
settings = Settings()
