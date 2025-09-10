"""
Configuration service.

This module provides unified configuration management combining
environment variables and database configurations.
"""

import os
from typing import Any, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from crud.system.config import system_configs
from enums import ConfigType


class ConfigService:
    """Unified configuration service."""

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_enabled = True

    async def get_config(
        self, db: AsyncSession, key: str, default: Any = None, use_cache: bool = True
    ) -> Any:
        """
        Get configuration value with fallback priority:
        1. Environment variable (if exists)
        2. Database configuration
        3. Default value
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
        db_value = await system_configs.get_config_value(db, config_key=key, default_value=default)

        if use_cache and self._cache_enabled:
            self._cache[key] = db_value

        return db_value

    async def get_leancloud_config(self, db: AsyncSession) -> Dict[str, Any]:
        """Get all LeanCloud configuration."""
        config = {
            "app_id": await self.get_config(db, "leancloud_app_id", ""),
            "app_key": await self.get_config(db, "leancloud_app_key", ""),
            "master_key": settings.LEANCLOUD_MASTER_KEY,  # Always from env
            "server_url": await self.get_config(db, "leancloud_server_url", None),
            "base_url": await self.get_config(db, "leancloud_base_url", "https://api.leancloud.cn"),
            "webhook_enabled": await self.get_config(db, "leancloud_webhook_enabled", True),
            "message_timeout_seconds": await self.get_config(db, "leancloud_message_timeout_seconds", 30),
            "retry_max_count": await self.get_config(db, "leancloud_retry_max_count", 3),
            "conversation_ttl_hours": await self.get_config(db, "leancloud_conversation_ttl_hours", 24),
        }
        return config

    async def update_config(
        self, db: AsyncSession, key: str, value: str, updated_by: Optional[int] = None
    ) -> bool:
        """Update configuration value in database."""
        try:
            result = await system_configs.update_config_value(
                db, config_key=key, config_value=value, updated_by=updated_by
            )

            # Clear cache for this key
            if self._cache_enabled and key in self._cache:
                del self._cache[key]

            return result is not None
        except Exception:
            return False

    async def batch_update_leancloud_config(
        self, db: AsyncSession, config_updates: Dict[str, str], updated_by: Optional[int] = None
    ) -> bool:
        """Batch update LeanCloud configuration."""
        try:
            for key, value in config_updates.items():
                config_key = f"leancloud_{key}"
                await system_configs.update_config_value(
                    db, config_key=config_key, config_value=value, updated_by=updated_by
                )

                # Clear cache
                if self._cache_enabled and config_key in self._cache:
                    del self._cache[config_key]

            return True
        except Exception:
            return False

    def clear_cache(self, key: Optional[str] = None):
        """Clear configuration cache."""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    def disable_cache(self):
        """Disable configuration caching."""
        self._cache_enabled = False
        self._cache.clear()

    def enable_cache(self):
        """Enable configuration caching."""
        self._cache_enabled = True


# Global configuration service instance
config_service = ConfigService()
