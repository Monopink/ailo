"""
Admin module configuration.
Integrates with main project settings.
"""

import os
from typing import List

# Import main project settings
from core.config import settings as main_settings


class AdminSettings:
    """Admin module settings that integrate with main project"""

    # Admin app info
    VERSION: str = "0.0.1"
    APP_TITLE: str = "Says Admin"
    PROJECT_NAME: str = "Says Admin"
    APP_DESCRIPTION: str = "Says Admin"

    # CORS settings for admin module
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",  # Main frontend
        "http://127.0.0.1:5173",  # Main frontend
        "http://localhost:5174",  # Admin frontend
        "http://127.0.0.1:5174",  # Admin frontend
        "http://localhost:8000",  # Backend
        "http://127.0.0.1:8000",  # Backend
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Debug and logging settings - read from environment variables
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Use main project's security settings
    SECRET_KEY: str = main_settings.SECRET_KEY
    JWT_ALGORITHM: str = main_settings.ALGORITHM
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = main_settings.ACCESS_TOKEN_EXPIRE_MINUTES
    # Database configuration - use main project's database
    DATABASE_URL: str = main_settings.database_url

    # Date/time format
    DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"

    # Admin-specific settings
    ADMIN_PAGE_SIZE: int = 20
    ADMIN_MAX_PAGE_SIZE: int = 100


# Create admin settings instance
admin_settings = AdminSettings()
