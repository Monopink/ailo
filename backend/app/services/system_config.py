"""
System configuration management service.

This module provides centralized management for system configuration
stored in the database, with caching and type conversion support.

IMPORTANT: This service is READ-ONLY. For write operations, use crud.system.config.
After updating configs through CRUD, call SystemConfigService.reload_cache() to sync.
"""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import MissingConfigurationError
from app.models.system import SystemConfig
from app.type_defs import ConfigGroup
from app.utils.logging import get_logger

logger = get_logger(__name__)


# Configuration cache
_config_cache: dict[str, Any] = {}
_cache_loaded = False


class SystemConfigService:
    """System configuration service with caching support."""

    @staticmethod
    async def get_config(db: AsyncSession, key: str, *, required: bool = True) -> Any:
        """
        Get configuration value by key.

        Args:
            db: Database session
            key: Configuration key
            required: Whether to raise if configuration is missing

        Returns:
            Configuration value with proper type conversion
        """
        global _config_cache, _cache_loaded

        # Load cache if not loaded
        if not _cache_loaded:
            await SystemConfigService._load_cache(db)

        # Return from cache
        if key in _config_cache:
            return _config_cache[key]

        # Missing configuration
        if required:
            logger.error("system_config_missing", key=key)
            raise MissingConfigurationError(config_key=key)

        logger.debug("system_config_optional_missing", key=key)
        return None

    @staticmethod
    async def get_all_configs(db: AsyncSession) -> dict[str, Any]:
        """
        Get all configuration values.

        Args:
            db: Database session

        Returns:
            Dictionary of all configuration values
        """
        global _config_cache, _cache_loaded

        if not _cache_loaded:
            await SystemConfigService._load_cache(db)

        return _config_cache.copy()

    @staticmethod
    async def get_configs_by_group(db: AsyncSession) -> dict[str, ConfigGroup]:
        """
        Get configurations grouped by group_name (fully dynamic from database).

        Returns:
            Grouped configuration dictionary with full config objects
        """
        # Get all config objects from database, ordered by group and key
        result = await db.execute(
            select(SystemConfig).order_by(SystemConfig.group_name, SystemConfig.config_key)
        )
        all_configs = result.scalars().all()

        # Dynamically build groups from database
        groups: dict[str, ConfigGroup] = {}
        for config in all_configs:
            group_name = config.group_name or "other"

            # Create group if not exists
            if group_name not in groups:
                groups[group_name] = ConfigGroup(
                    title=group_name,  # Will be formatted by frontend
                    description="",
                    configs={},
                )

            # Add config to group
            groups[group_name]["configs"][config.config_key] = config

        return groups

    @staticmethod
    async def check_missing_configs(db: AsyncSession, displayed_keys: set[str]) -> list[str]:
        """
        Check if all configs in database are displayed in UI.

        Args:
            db: Database session
            displayed_keys: Set of config keys currently displayed

        Returns:
            List of missing config keys
        """
        try:
            result = await db.execute(select(SystemConfig.config_key))
            all_keys = {row[0] for row in result.fetchall()}
            missing_keys = all_keys - displayed_keys
            return sorted(missing_keys)
        except Exception as e:
            logger.error("check_missing_configs_error", error=str(e), exc_info=True)
            return []

    @staticmethod
    async def reload_cache(db: AsyncSession) -> None:
        """
        Reload configuration cache from database.

        This should be called after updating configurations through CRUD layer
        to ensure cache consistency.
        """
        global _cache_loaded
        _cache_loaded = False
        await SystemConfigService._load_cache(db)

    @staticmethod
    async def _load_cache(db: AsyncSession) -> None:
        """Load all configurations into cache."""
        global _config_cache, _cache_loaded

        try:
            result = await db.execute(select(SystemConfig))
            configs = result.scalars().all()

            _config_cache.clear()
            for config in configs:
                value = SystemConfigService._convert_from_db_format(
                    config.config_value, config.config_type
                )
                _config_cache[config.config_key] = value

            _cache_loaded = True
            logger.info("system_configs_cache_loaded", count=len(_config_cache))

        except Exception as e:
            logger.error("system_configs_cache_load_error", error=str(e), exc_info=True)
            _cache_loaded = False

    @staticmethod
    def _convert_to_db_format(value: Any) -> tuple[str, int]:
        """
        Convert Python value to database format.

        Returns:
            Tuple of (string_value, config_type)
            config_type: 1=string, 2=integer, 3=boolean, 4=json
        """
        if isinstance(value, bool):
            return str(value).lower(), 3
        if isinstance(value, int):
            return str(value), 2
        if isinstance(value, list | dict):
            return json.dumps(value), 4
        return str(value), 1

    @staticmethod
    def _convert_from_db_format(value: str | None, config_type: int) -> Any:
        """
        Convert database value to Python type.

        Args:
            value: String value from database
            config_type: 1=string, 2=integer, 3=boolean, 4=json

        Returns:
            Converted Python value
        """
        if value is None:
            return None

        try:
            if config_type == 1:  # string
                return value
            if config_type == 2:  # integer
                return int(value)
            if config_type == 3:  # boolean
                return value.lower() in ("true", "1", "yes", "on")
            if config_type == 4:  # json
                return json.loads(value)
            return value
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(
                "system_configs_conversion_error",
                value=value,
                config_type=config_type,
                error=str(e),
            )
            return value


# Convenience functions
async def get_config(db: AsyncSession, key: str, *, required: bool = True) -> Any:
    """Get configuration value."""
    return await SystemConfigService.get_config(db, key, required=required)


async def get_all_configs(db: AsyncSession) -> dict[str, Any]:
    """Get all configuration values."""
    return await SystemConfigService.get_all_configs(db)


async def get_configs_by_group(db: AsyncSession) -> dict[str, ConfigGroup]:
    """Get configurations grouped by category."""
    return await SystemConfigService.get_configs_by_group(db)
