from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Configuration is now purely environment variable driven
    # No env_file dependency - all variables must be provided via environment
    model_config = SettingsConfigDict(extra="ignore")

    PROJECT_NAME: str = "Says Contacts Service"

    # Database settings
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # LeanCloud settings
    LEANCLOUD_APP_ID: str
    LEANCLOUD_APP_KEY: str
    LEANCLOUD_MASTER_KEY: str
    LEANCLOUD_BASE_URL: str

    # User contact limits
    DEFAULT_CONTACT_LIMIT: int = 1
    DEFAULT_SEARCH_DISPLAY_LIMIT: int = 2
    ADD_CONTACT_TIMEOUT: int = 300

    # Entity ID settings
    ENTITY_ID_PREFIX: str = "qqid_"

    # Internal service authentication
    INTERNAL_SERVICE_KEY: str = "default_internal_key_change_me"

    @property
    def database_url(self) -> str:
        """
        Constructs the database URL from settings.
        """
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


# Create a single settings instance to be used across the application
settings = Settings()
