"""
Configuration service.

This module provides unified configuration management combining
environment variables and database configurations.

READ-ONLY service for configuration retrieval with caching.
For write operations, use crud.system.config and reload cache.
"""

import os
from typing import Any, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from services.system_config import SystemConfigService


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
        db_value = await SystemConfigService.get_config(db, key, default)

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

    async def get_int(self, db: AsyncSession, key: str, default: int = 0) -> int:
        """Get configuration as integer with safe coercion."""
        try:
            value = await self.get_config(db, key, default)
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def clear_cache(self, key: Optional[str] = None) -> None:
        """
        Clear configuration cache.

        Note: This only clears ConfigService cache, not SystemConfigService cache.
        To reload system configs, use SystemConfigService.reload_cache().
        """
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
