"""System configuration management service.

This module provides centralized management for system configuration
stored in the database, with caching and type conversion support.

IMPORTANT: This service is READ-ONLY. For write operations, use crud.system.config.
After updating configs through CRUD, call SystemConfigService.reload_cache() to sync.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ConfigShape, ConfigValueType
from app.exceptions import ConfigurationError, MissingConfigurationError
from app.models.system import SystemConfig
from app.type_defs import ConfigGroup, JSONValue
from app.utils.logging import get_logger

logger = get_logger(__name__)

ConfigValue = JSONValue | None
NumericConfigValue = str | int | float


class _ConfigCacheState(TypedDict):
    cache: dict[str, ConfigValue]
    loaded: bool
    last_version_check_at: datetime | None


_CACHE_VERSION_CHECK_INTERVAL = timedelta(seconds=5)

_config_state: _ConfigCacheState = {
    "cache": {},
    "loaded": False,
    "last_version_check_at": None,
}


def _ensure_numeric_config_value(value: ConfigValue, key: str) -> NumericConfigValue:
    """Ensure a configuration value can be treated as a numeric string/int."""
    if isinstance(value, str | int | float) and not isinstance(value, bool):
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


def _ensure_bool_config_value(value: ConfigValue, key: str) -> bool:
    """Ensure a configuration value can be treated as a boolean."""
    if isinstance(value, bool):
        return value
    raise ConfigurationError(
        message=f"Configuration '{key}' expects a boolean value.",
        config_key=key,
        details={"received_type": type(value).__name__ if value is not None else "None"},
    )


def _ensure_string_list_config_value(value: ConfigValue, key: str) -> list[str]:
    """Ensure a configuration value can be treated as a non-empty list of strings."""
    if not isinstance(value, list):
        raise ConfigurationError(
            message=f"Configuration '{key}' expects a string array.",
            config_key=key,
            details={"received_type": type(value).__name__ if value is not None else "None"},
        )

    normalized_items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ConfigurationError(
                message=f"Configuration '{key}' contains non-string array item.",
                config_key=key,
                details={"index": index, "received_type": type(item).__name__},
            )
        trimmed_item = item.strip()
        if trimmed_item == "":
            raise ConfigurationError(
                message=f"Configuration '{key}' contains empty string array item.",
                config_key=key,
                details={"index": index},
            )
        normalized_items.append(trimmed_item)

    if len(normalized_items) == 0:
        raise ConfigurationError(
            message=f"Configuration '{key}' must contain at least one string item.",
            config_key=key,
            details={"received_length": 0},
        )

    return normalized_items


class SystemConfigService:
    """System configuration service with caching support."""

    @staticmethod
    async def get_config(db: AsyncSession, key: str, *, required: bool = True) -> ConfigValue:
        """Get configuration value by key."""
        if not _config_state["loaded"]:
            await SystemConfigService._load_cache(db)
        else:
            await SystemConfigService._maybe_reload_cache_if_stale(db)

        if key in _config_state["cache"]:
            return _config_state["cache"][key]

        db_value = await SystemConfigService._get_config_value_from_db(db, key)
        if db_value is not None:
            _config_state["cache"][key] = db_value
            logger.info("system_config_cache_miss_db_hit", key=key)
            return db_value

        logger.warning("system_config_cache_miss_db_miss", key=key)
        if required:
            logger.error("system_config_missing", key=key)
            raise MissingConfigurationError(config_key=key)

        logger.debug("system_config_optional_missing", key=key)
        return None

    @staticmethod
    async def get_config_int(
        db: AsyncSession,
        key: str,
        *,
        required: bool = True,
    ) -> int:
        """Get a configuration value as an integer."""
        value = await SystemConfigService.get_config(db, key, required=required)
        if value is None:
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
        required: bool = True,
    ) -> str:
        """Get a configuration value as a string."""
        value = await SystemConfigService.get_config(db, key, required=required)
        if value is None:
            raise MissingConfigurationError(config_key=key)
        return _ensure_string_config_value(value, key)

    @staticmethod
    async def get_config_time_str(
        db: AsyncSession,
        key: str,
        *,
        required: bool = True,
    ) -> str:
        """Get a configuration value as normalized UTC ISO8601 datetime string."""
        value = await SystemConfigService.get_config(db, key, required=required)
        if value is None:
            if required:
                raise MissingConfigurationError(config_key=key)
            return ""
        if not isinstance(value, str):
            raise ConfigurationError(
                message=f"Configuration '{key}' expects an ISO8601 datetime string.",
                config_key=key,
                details={"received_type": type(value).__name__},
            )
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ConfigurationError(
                message=f"Configuration '{key}' expects an ISO8601 datetime string.",
                config_key=key,
                details={"value": value},
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)
        return parsed.isoformat().replace("+00:00", "Z")

    @staticmethod
    async def get_config_bool(
        db: AsyncSession,
        key: str,
        *,
        required: bool = True,
    ) -> bool:
        """Get a configuration value as a boolean."""
        value = await SystemConfigService.get_config(db, key, required=required)
        if value is None:
            raise MissingConfigurationError(config_key=key)
        return _ensure_bool_config_value(value, key)

    @staticmethod
    async def get_config_str_list(
        db: AsyncSession,
        key: str,
        *,
        required: bool = True,
    ) -> list[str]:
        """Get a configuration value as a non-empty list of strings."""
        value = await SystemConfigService.get_config(db, key, required=required)
        if value is None:
            if required:
                raise MissingConfigurationError(config_key=key)
            return []
        return _ensure_string_list_config_value(value, key)

    @staticmethod
    async def get_all_configs(db: AsyncSession) -> dict[str, ConfigValue]:
        """Get all configuration values."""
        if not _config_state["loaded"]:
            await SystemConfigService._load_cache(db)
        else:
            await SystemConfigService._maybe_reload_cache_if_stale(db)
        return _config_state["cache"].copy()

    @staticmethod
    async def get_configs_by_group(db: AsyncSession) -> dict[str, ConfigGroup]:
        """Get configurations grouped by group_name."""
        return await SystemConfigService.get_configs_by_group_with_scope(db)

    @staticmethod
    async def get_configs_by_group_with_scope(
        db: AsyncSession,
        *,
        scopes: set[str] | None = None,
    ) -> dict[str, ConfigGroup]:
        """Get configurations grouped by group_name with optional scope filter."""
        stmt = select(SystemConfig)
        if scopes:
            stmt = stmt.where(SystemConfig.config_scope.in_(scopes))
        result = await db.execute(stmt.order_by(SystemConfig.group_name, SystemConfig.config_key))
        all_configs = result.scalars().all()

        groups: dict[str, ConfigGroup] = {}
        for config in all_configs:
            group_name = config.group_name or "other"
            if group_name not in groups:
                groups[group_name] = ConfigGroup(
                    title=group_name,
                    description="",
                    configs={},
                )
            groups[group_name]["configs"][config.config_key] = config
        return groups

    @staticmethod
    async def check_missing_configs(db: AsyncSession, displayed_keys: set[str]) -> list[str]:
        """Check if all configs in database are displayed in UI."""
        try:
            result = await db.execute(select(SystemConfig.config_key))
            all_keys = {row[0] for row in result.fetchall()}
            missing_keys = all_keys - displayed_keys
            return sorted(missing_keys)
        except Exception as exc:
            logger.error("check_missing_configs_error", error=str(exc), exc_info=True)
            return []

    @staticmethod
    async def reload_cache(db: AsyncSession) -> None:
        """Reload configuration cache from database."""
        _config_state["loaded"] = False
        await SystemConfigService._load_cache(db)

    @staticmethod
    async def _maybe_reload_cache_if_stale(db: AsyncSession) -> None:
        """Reload cache periodically to guarantee eventual consistency across instances."""
        now = datetime.now(UTC)
        last_check = _config_state["last_version_check_at"]
        if last_check is not None and now - last_check < _CACHE_VERSION_CHECK_INTERVAL:
            return

        try:
            await SystemConfigService._load_cache(db)
        except Exception as exc:
            logger.warning("system_configs_periodic_reload_failed", error=str(exc), exc_info=True)
        else:
            logger.info("system_configs_cache_periodic_reloaded")

    @staticmethod
    async def _load_cache(db: AsyncSession) -> None:
        """Load all configurations into cache."""
        try:
            result = await db.execute(
                select(SystemConfig).execution_options(populate_existing=True)
            )
            configs = result.scalars().all()

            cache = _config_state["cache"]
            cache.clear()
            for config in configs:
                value = SystemConfigService._convert_from_db_format(
                    config.config_value,
                    config.value_type,
                    config_shape=config.config_shape,
                    config_key=config.config_key,
                )
                cache[config.config_key] = value

            _config_state["loaded"] = True
            _config_state["last_version_check_at"] = datetime.now(UTC)
            logger.info("system_configs_cache_loaded", count=len(cache))
        except Exception as exc:
            logger.error("system_configs_cache_load_error", error=str(exc), exc_info=True)
            _config_state["loaded"] = False
            raise

    @staticmethod
    async def _get_config_value_from_db(db: AsyncSession, key: str) -> ConfigValue:
        """Fetch and convert one configuration value directly from database."""
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.config_key == key).limit(1)
        )
        config = result.scalar_one_or_none()
        if config is None:
            return None

        return SystemConfigService._convert_from_db_format(
            config.config_value,
            config.value_type,
            config_shape=config.config_shape,
            config_key=config.config_key,
        )

    @staticmethod
    def _convert_time_single_value(
        *,
        value: JSONValue,
        config_key: str,
        value_type: int,
    ) -> str | None:
        """Convert one TIME value to normalized UTC ISO8601 string."""
        if not isinstance(value, str):
            raise ConfigurationError(
                message="Configuration expects an ISO8601 datetime string.",
                config_key=config_key,
                details={"value": value, "value_type": int(value_type)},
            )
        raw_value = value.strip()
        if raw_value == "":
            return None
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ConfigurationError(
                message="Configuration expects an ISO8601 datetime string.",
                config_key=config_key,
                details={"value": value, "value_type": int(value_type)},
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)
        return parsed.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _convert_single_value(  # noqa: PLR0911
        value: JSONValue,
        value_type: int,
        *,
        config_key: str,
    ) -> JSONValue:
        """Convert one JSONB scalar value to runtime type."""
        if value_type in (ConfigValueType.STRING, ConfigValueType.ENUM):
            if isinstance(value, str):
                return value
            raise ConfigurationError(
                message="Configuration expects a string value.",
                config_key=config_key,
                details={"value": value, "value_type": int(value_type)},
            )

        if value_type == ConfigValueType.TIME:
            return SystemConfigService._convert_time_single_value(
                value=value,
                config_key=config_key,
                value_type=value_type,
            )

        if value_type == ConfigValueType.NUMBER:
            if isinstance(value, bool):
                raise ConfigurationError(
                    message="Configuration expects an integer value.",
                    config_key=config_key,
                    details={"value": value, "value_type": int(value_type)},
                )
            if isinstance(value, int):
                return value
            if isinstance(value, float) and value.is_integer():
                return int(value)
            if isinstance(value, str):
                raw_value = value.strip()
                if raw_value == "":
                    raise ConfigurationError(
                        message="Configuration expects an integer value.",
                        config_key=config_key,
                        details={"value": value, "value_type": int(value_type)},
                    )
                try:
                    return int(raw_value)
                except (ValueError, TypeError) as exc:
                    raise ConfigurationError(
                        message="Configuration expects an integer value.",
                        config_key=config_key,
                        details={"value": value, "value_type": int(value_type)},
                    ) from exc
            raise ConfigurationError(
                message="Configuration expects an integer value.",
                config_key=config_key,
                details={"value": value, "value_type": int(value_type)},
            )

        if value_type == ConfigValueType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.lower()
                if lowered in ("true", "1", "yes", "on"):
                    return True
                if lowered in ("false", "0", "no", "off"):
                    return False
            raise ConfigurationError(
                message="Configuration expects a boolean value.",
                config_key=config_key,
                details={"value": value, "value_type": int(value_type)},
            )

        if value_type == ConfigValueType.JSON:
            return value

        return value

    @staticmethod
    def _convert_from_db_format(
        value: JSONValue | None,
        value_type: int,
        *,
        config_shape: int,
        config_key: str,
    ) -> ConfigValue:
        """Convert database JSONB value to runtime type."""
        if value is None:
            return None

        if config_shape == ConfigShape.ARRAY:
            if not isinstance(value, list):
                raise ConfigurationError(
                    message="Configuration expects an array value.",
                    config_key=config_key,
                    details={"value": value, "config_shape": int(config_shape)},
                )

            converted_items: list[JSONValue] = []
            for item in value:
                converted_items.append(
                    SystemConfigService._convert_single_value(
                        item,
                        value_type,
                        config_key=config_key,
                    )
                )
            return converted_items

        return SystemConfigService._convert_single_value(
            value,
            value_type,
            config_key=config_key,
        )


async def get_config(db: AsyncSession, key: str, *, required: bool = True) -> ConfigValue:
    """Get configuration value."""
    return await SystemConfigService.get_config(db, key, required=required)


async def get_config_int(
    db: AsyncSession,
    key: str,
    *,
    required: bool = True,
) -> int:
    """Get configuration value as an integer."""
    return await SystemConfigService.get_config_int(db, key, required=required)


async def get_config_str(
    db: AsyncSession,
    key: str,
    *,
    required: bool = True,
) -> str:
    """Get configuration value as a string."""
    return await SystemConfigService.get_config_str(db, key, required=required)


async def get_config_time_str(
    db: AsyncSession,
    key: str,
    *,
    required: bool = True,
) -> str:
    """Get configuration value as normalized UTC ISO8601 datetime string."""
    return await SystemConfigService.get_config_time_str(db, key, required=required)


async def get_config_bool(
    db: AsyncSession,
    key: str,
    *,
    required: bool = True,
) -> bool:
    """Get configuration value as a boolean."""
    return await SystemConfigService.get_config_bool(db, key, required=required)


async def get_config_str_list(
    db: AsyncSession,
    key: str,
    *,
    required: bool = True,
) -> list[str]:
    """Get configuration value as a non-empty list of strings."""
    return await SystemConfigService.get_config_str_list(db, key, required=required)


async def get_all_configs(db: AsyncSession) -> dict[str, ConfigValue]:
    """Get all configuration values."""
    return await SystemConfigService.get_all_configs(db)


async def get_configs_by_group(db: AsyncSession) -> dict[str, ConfigGroup]:
    """Get configurations grouped by category."""
    return await SystemConfigService.get_configs_by_group(db)


async def get_configs_by_group_with_scope(
    db: AsyncSession,
    *,
    scopes: set[str] | None = None,
) -> dict[str, ConfigGroup]:
    """Get configurations grouped by category with optional scope filter."""
    return await SystemConfigService.get_configs_by_group_with_scope(db, scopes=scopes)
