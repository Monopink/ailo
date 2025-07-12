from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "SAYS Account Service"

    # JWT settings
    # To generate a new secret key:
    # openssl rand -hex 32
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # Database settings from .env file
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # User contact limits
    DEFAULT_CONTACT_LIMIT: int = 1
    DEFAULT_SEARCH_DISPLAY_LIMIT: int = 2

    # Entity ID settings
    ENTITY_ID_PREFIX: str = "qqid_"

    # This will be assembled from the variables above
    DATABASE_URL: str = ""

    @model_validator(mode="after")
    def assemble_db_connection(self) -> "Settings":
        """Assembles the database connection string."""
        self.DATABASE_URL = (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
        return self

    class Config:
        # This tells pydantic-settings to load variables from a .env file
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Create a single instance of the settings
settings = Settings()
