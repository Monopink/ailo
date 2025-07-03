from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # This tells pydantic to load variables from the .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    @property
    def database_url(self) -> str:
        """
        Constructs the database URL from settings.
        """
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


# Create a single settings instance to be used across the application
settings = Settings()
