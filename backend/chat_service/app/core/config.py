from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any, Dict, Optional


class Settings(BaseSettings):
    # This tells pydantic to load variables from the .env file
    model_config = SettingsConfigDict(env_file="../../../.env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "Says Chat Service"

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

    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return (
            f"mysql+aiomysql://{values.get('MYSQL_USER')}:{values.get('MYSQL_PASSWORD')}@"
            f"{values.get('MYSQL_SERVER')}:{values.get('MYSQL_PORT')}/{values.get('MYSQL_DB')}"
        )


# Create a single settings instance to be used across the application
settings = Settings()
