"""
System configuration management service.

This module provides centralized management for system configuration
stored in the database, with caching and type conversion support.

IMPORTANT: This service is READ-ONLY. For write operations, use crud.system.config.
After updating configs through CRUD, call SystemConfigService.reload_cache() to sync.
"""

import json
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ConfigType
from app.exceptions import ConfigurationError, MissingConfigurationError
from app.models.system import SystemConfig
from app.type_defs import ConfigGroup, JSONValue
from app.utils.logging import get_logger

logger = get_logger(__name__)


# Configuration cache
ConfigValue = JSONValue | None
NumericConfigValue = str | int | float


class _ConfigCacheState(TypedDict):
    cache: dict[str, ConfigValue]
    loaded: bool


_config_state: _ConfigCacheState = {"cache": {}, "loaded": False}


def _ensure_numeric_config_value(value: ConfigValue, key: str) -> NumericConfigValue:
    """Ensure a configuration value can be treated as a numeric string/int."""
    if isinstance(value, str | int | float):
        return value
    raise ConfigurationError(
        message=f"Configuration '{key}' expects a numeric value.",
        config_key=key,
        details={"received_type": type(value).__name__},
    )


def _ensure_string_config_value(value: ConfigValue, key: str) -> str:
    """Ensure a configuration value can be treated as a string."""
    if isinstance(value, str):
        return value
    raise ConfigurationError(
        message=f"Configuration '{key}' expects a string value.",
        config_key=key,
        details={"received_type": type(value).__name__ if value is not None else "None"},
    )


class SystemConfigService:
    """System configuration service with caching support."""

    @staticmethod
    async def get_config(db: AsyncSession, key: str, *, required: bool = True) -> ConfigValue:
        """
        Get configuration value by key.

        Args:
            db: Database session
            key: Configuration key
            required: Whether to raise if configuration is missing

        Returns:
            Configuration value with proper type conversion
        """
        # Load cache if not loaded
        if not _config_state["loaded"]:
            await SystemConfigService._load_cache(db)

        # Return from cache
        if key in _config_state["cache"]:
            return _config_state["cache"][key]

        # Missing configuration
        if required:
            logger.warning("system_config_missing_retry_reload", key=key)
            await SystemConfigService.reload_cache(db)
            if key in _config_state["cache"]:
                logger.info("system_config_loaded_after_reload", key=key)
                return _config_state["cache"][key]
            logger.error("system_config_missing", key=key)
            raise MissingConfigurationError(config_key=key)

        logger.debug("system_config_optional_missing", key=key)
        return None

    @staticmethod
    async def get_config_int(
        db: AsyncSession,
        key: str,
        *,
        default: int | None = None,
        required: bool = True,
    ) -> int:
        """Get a configuration value as an integer."""
        value = await SystemConfigService.get_config(db, key, required=required)
        if value is None:
            if default is not None:
                return default
            raise MissingConfigurationError(config_key=key)

        numeric_value = _ensure_numeric_config_value(value, key)
        try:
            return int(numeric_value)
        except (ValueError, TypeError) as exc:
            raise ConfigurationError(
                message=f"Configuration '{key}' contains non-integer data.",
                config_key=key,
                details={"value": numeric_value},
            ) from exc

    @staticmethod
    async def get_config_str(
        db: AsyncSession,
        key: str,
        *,
        default: str | None = None,
        required: bool = True,
    ) -> str:
        """Get a configuration value as a string."""
        value = await SystemConfigService.get_config(db, key, required=required)
        if value is None:
            if default is not None:
                return default
            raise MissingConfigurationError(config_key=key)

        return _ensure_string_config_value(value, key)

    @staticmethod
    async def get_all_configs(db: AsyncSession) -> dict[str, ConfigValue]:
        """
        Get all configuration values.

        Args:
            db: Database session

        Returns:
            Dictionary of all configuration values
        """
        if not _config_state["loaded"]:
            await SystemConfigService._load_cache(db)

        return _config_state["cache"].copy()

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
        _config_state["loaded"] = False
        await SystemConfigService._load_cache(db)

    @staticmethod
    async def _load_cache(db: AsyncSession) -> None:
        """Load all configurations into cache."""
        try:
            result = await db.execute(select(SystemConfig))
            configs = result.scalars().all()

            cache = _config_state["cache"]
            cache.clear()
            for config in configs:
                value = SystemConfigService._convert_from_db_format(
                    config.config_value, config.config_type
                )
                cache[config.config_key] = value

            _config_state["loaded"] = True
            logger.info("system_configs_cache_loaded", count=len(cache))

        except Exception as e:
            logger.error("system_configs_cache_load_error", error=str(e), exc_info=True)
            _config_state["loaded"] = False

    @staticmethod
    def _convert_to_db_format(value: ConfigValue) -> tuple[str, int]:
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
    def _convert_from_db_format(value: str | None, config_type: int) -> ConfigValue:
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
            if config_type == ConfigType.STRING:
                converted: ConfigValue = value
            elif config_type == ConfigType.NUMBER:
                converted = int(value)
            elif config_type == ConfigType.BOOLEAN:
                converted = value.lower() in ("true", "1", "yes", "on")
            elif config_type == ConfigType.JSON:
                converted = json.loads(value)
            else:
                converted = value
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(
                "system_configs_conversion_error",
                value=value,
                config_type=config_type,
                error=str(e),
            )
            converted = value

        return converted


# Convenience functions
async def get_config(db: AsyncSession, key: str, *, required: bool = True) -> ConfigValue:
    """Get configuration value."""
    return await SystemConfigService.get_config(db, key, required=required)


async def get_config_int(
    db: AsyncSession,
    key: str,
    *,
    default: int | None = None,
    required: bool = True,
) -> int:
    """Get configuration value as an integer."""
    return await SystemConfigService.get_config_int(
        db,
        key,
        default=default,
        required=required,
    )


async def get_config_str(
    db: AsyncSession,
    key: str,
    *,
    default: str | None = None,
    required: bool = True,
) -> str:
    """Get configuration value as a string."""
    return await SystemConfigService.get_config_str(
        db,
        key,
        default=default,
        required=required,
    )


async def get_all_configs(db: AsyncSession) -> dict[str, ConfigValue]:
    """Get all configuration values."""
    return await SystemConfigService.get_all_configs(db)


async def get_configs_by_group(db: AsyncSession) -> dict[str, ConfigGroup]:
    """Get configurations grouped by category."""
    return await SystemConfigService.get_configs_by_group(db)
