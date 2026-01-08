"""
Configuration service.

This module provides unified configuration management combining
environment variables and database configurations.

READ-ONLY service for configuration retrieval with caching.
For write operations, use crud.system.config and reload cache.
"""

import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.exceptions import ConfigurationError, MissingConfigurationError
from app.services.system_config import SystemConfigService
from app.type_defs import JSONValue


class ConfigService:
    """Unified configuration service."""

    def __init__(self) -> None:
        self._cache: dict[str, JSONValue | None] = {}
        self._cache_enabled = True

    async def get_config(
        self, db: AsyncSession, key: str, *, use_cache: bool = True, required: bool = True
    ) -> JSONValue | None:
        """
        Get configuration value with fallback priority:
        1. Environment variable (if exists)
        2. Database configuration
        """
        # Check cache first
        if use_cache and self._cache_enabled and key in self._cache:
            return self._cache[key]

        # Check environment variable first
        env_value = os.getenv(key.upper())
        if env_value is not None:
            if use_cache and self._cache_enabled:
                self._cache[key] = env_value
            return env_value

        # Check database configuration
        db_value = await SystemConfigService.get_config(db, key, required=required)

        if use_cache and self._cache_enabled:
            self._cache[key] = db_value

        return db_value

    async def get_leancloud_config(self, db: AsyncSession) -> dict[str, str | None]:
        """
        Get all LeanCloud IM configuration.

        Returns configuration values as-is (may contain None for missing configs).
        Callers are responsible for validating completeness based on their needs.
        """
        return {
            "app_id": self._coerce_to_str(
                await self.get_config(db, "leancloud_im_app_id", required=False)
            ),
            "app_key": self._coerce_to_str(
                await self.get_config(db, "leancloud_im_app_key", required=False)
            ),
            "master_key": get_settings().LEANCLOUD_MASTER_KEY,  # Always from env
            "base_url": self._coerce_to_str(
                await self.get_config(db, "leancloud_im_server_url", required=False)
            ),
        }

    def _coerce_to_str(self, value: JSONValue | None) -> str | None:
        if value is None:
            return None
        return str(value)

    async def get_int(self, db: AsyncSession, key: str, *, required: bool = True) -> int:
        """Get configuration as integer with strict coercion."""
        try:
            value = await self.get_config(db, key, required=required)
            if value is None:
                raise MissingConfigurationError(config_key=key)
            if isinstance(value, (int, float, str)):
                return int(value)
            raise TypeError(f"Unsupported type for integer configuration: {type(value).__name__}")
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                message=f"Configuration '{key}' must be an integer",
                config_key=key,
                details={"value": value},
            ) from exc

    def clear_cache(self, key: str | None = None) -> None:
        """
        Clear configuration cache.

        Note: This only clears ConfigService cache, not SystemConfigService cache.
        To reload system configs, use SystemConfigService.reload_cache().
        """
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    def disable_cache(self) -> None:
        """Disable configuration caching."""
        self._cache_enabled = False
        self._cache.clear()

    def enable_cache(self) -> None:
        """Enable configuration caching."""
        self._cache_enabled = True


# Global configuration service instance
config_service = ConfigService()
