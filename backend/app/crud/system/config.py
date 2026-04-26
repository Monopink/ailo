"""System configuration CRUD operations."""

from __future__ import annotations

import json
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.enums import ConfigShape, ConfigValueType
from app.models.system import SystemConfig
from app.schemas.system import SystemConfigCreate, SystemConfigUpdate
from app.type_defs import JSONValue
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CRUDSystemConfig(CRUDBase[SystemConfig, SystemConfigCreate, SystemConfigUpdate]):
    """CRUD operations for SystemConfig model."""

    @staticmethod
    def _parse_json_value(*, config_key: str, config_value: str) -> JSONValue:
        """Parse JSON value from a string input."""
        raw_value = config_value.strip()
        try:
            parsed = cast(JSONValue, json.loads(raw_value))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid value '{config_value}' for {config_key}. Must be valid JSON."
            ) from exc
        return parsed

    @staticmethod
    def _ensure_json_serializable(*, config_key: str, config_value: JSONValue) -> JSONValue:
        """Ensure value can be serialized to JSONB without lossy conversion."""
        try:
            json.dumps(config_value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid value for {config_key}. Must be JSON serializable.") from exc
        return config_value

    @staticmethod
    def _normalize_single_value(  # noqa: PLR0911, PLR0912
        *,
        config_key: str,
        value_type: ConfigValueType,
        value: JSONValue | str,
        allowed_values: JSONValue | None,
        validate_enum: bool,
        allow_empty: bool,
    ) -> JSONValue:
        """Validate one single value by configured value_type."""
        if allow_empty and value is None:
            return None

        if value_type == ConfigValueType.NUMBER:
            if isinstance(value, bool):
                raise ValueError(f"Invalid value '{value}' for {config_key}. Must be integer.")
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                if not value.is_integer():
                    raise ValueError(f"Invalid value '{value}' for {config_key}. Must be integer.")
                return int(value)
            if isinstance(value, str):
                raw_value = value.strip()
                if raw_value == "":
                    if allow_empty:
                        return None
                    raise ValueError(f"Invalid value '{value}' for {config_key}. Must be integer.")
                try:
                    return int(raw_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid value '{value}' for {config_key}. Must be integer."
                    ) from exc
            raise ValueError(f"Invalid value '{value}' for {config_key}. Must be integer.")

        if value_type == ConfigValueType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized == "" and allow_empty:
                    return None
                if normalized in {"true", "1", "yes", "on"}:
                    return True
                if normalized in {"false", "0", "no", "off"}:
                    return False
            raise ValueError(
                f"Invalid value '{value}' for {config_key}. "
                "Allowed boolean literals: true/false/1/0/yes/no/on/off."
            )

        if value_type == ConfigValueType.JSON:
            if isinstance(value, str):
                raw_value = value.strip()
                if raw_value == "":
                    if allow_empty:
                        return None
                    raise ValueError(
                        f"Invalid value '{value}' for {config_key}. Must be valid JSON."
                    )
                parsed_json = CRUDSystemConfig._parse_json_value(
                    config_key=config_key,
                    config_value=raw_value,
                )
                return CRUDSystemConfig._ensure_json_serializable(
                    config_key=config_key,
                    config_value=parsed_json,
                )
            return CRUDSystemConfig._ensure_json_serializable(
                config_key=config_key,
                config_value=value,
            )

        if value_type == ConfigValueType.ENUM:
            raw_value = value.strip() if isinstance(value, str) else str(value).strip()
            if raw_value == "":
                if allow_empty:
                    return ""
                raise ValueError(f"Invalid value '{value}' for {config_key}.")
            if validate_enum:
                if not isinstance(allowed_values, list) or raw_value not in allowed_values:
                    allowed_str = (
                        [str(v) for v in allowed_values] if isinstance(allowed_values, list) else []
                    )
                    raise ValueError(
                        f"Invalid value '{value}' for {config_key}. "
                        f"Allowed values: {', '.join(allowed_str)}"
                    )
            return raw_value

        raw_value = value.strip() if isinstance(value, str) else str(value).strip()
        if raw_value == "":
            if allow_empty:
                return ""
            raise ValueError(f"Invalid value '{value}' for {config_key}.")
        return raw_value

    @staticmethod
    def _normalize_config_value(
        *,
        config_key: str,
        value_type: ConfigValueType,
        config_shape: ConfigShape,
        config_value: JSONValue | str,
        allowed_values: JSONValue | None,
        validate_enum: bool,
        allow_empty: bool,
    ) -> JSONValue:
        """Validate and normalize config value by configured value_type/config_shape."""
        if config_shape == ConfigShape.ARRAY:
            parsed_value = config_value
            if isinstance(config_value, str):
                parsed_value = CRUDSystemConfig._parse_json_value(
                    config_key=config_key,
                    config_value=config_value,
                )

            if not isinstance(parsed_value, list):
                raise TypeError(f"Invalid value for {config_key}. Must be JSON array.")

            normalized_items: list[JSONValue] = []
            for index, item in enumerate(parsed_value):
                normalized_item = CRUDSystemConfig._normalize_single_value(
                    config_key=f"{config_key}[{index}]",
                    value_type=value_type,
                    value=item,
                    allowed_values=allowed_values,
                    validate_enum=validate_enum,
                    allow_empty=False,
                )
                normalized_items.append(normalized_item)

            if len(normalized_items) == 0:
                if allow_empty:
                    return cast(JSONValue, normalized_items)
                raise ValueError(f"Invalid value for {config_key}. Must contain at least one item.")
            return cast(JSONValue, normalized_items)

        return CRUDSystemConfig._normalize_single_value(
            config_key=config_key,
            value_type=value_type,
            value=config_value,
            allowed_values=allowed_values,
            validate_enum=validate_enum,
            allow_empty=allow_empty,
        )

    @staticmethod
    def _normalize_stored_single_value(  # noqa: PLR0911
        *,
        config_key: str,
        value_type: ConfigValueType,
        value: JSONValue,
    ) -> JSONValue:
        """Normalize one stored JSONB value based on value_type."""
        if value_type == ConfigValueType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.lower()
                if lowered in {"true", "1", "yes", "on"}:
                    return True
                if lowered in {"false", "0", "no", "off"}:
                    return False
            raise ValueError(f"Invalid boolean configuration for '{config_key}': {value}")

        if value_type == ConfigValueType.NUMBER:
            if isinstance(value, bool):
                raise ValueError(f"Invalid number configuration for '{config_key}': {value}")
            if isinstance(value, int):
                return value
            if isinstance(value, float) and value.is_integer():
                return int(value)
            if isinstance(value, str):
                try:
                    return int(value.strip())
                except (TypeError, ValueError) as exc:
                    logger.error(
                        "config_number_parse_error",
                        config_key=config_key,
                        config_value=value,
                        error=str(exc),
                    )
                    raise ValueError(
                        f"Invalid number configuration for '{config_key}': {value}"
                    ) from exc
            raise ValueError(f"Invalid number configuration for '{config_key}': {value}")

        if value_type in {ConfigValueType.STRING, ConfigValueType.ENUM}:
            if isinstance(value, str):
                return value
            raise ValueError(f"Invalid string configuration for '{config_key}': {value}")

        return value

    async def get_by_key(self, db: AsyncSession, *, config_key: str) -> SystemConfig | None:
        """Get configuration by key."""
        result = await db.execute(select(self.model).where(self.model.config_key == config_key))
        return result.scalar_one_or_none()

    async def get_by_value_type(
        self, db: AsyncSession, *, value_type: ConfigValueType
    ) -> list[SystemConfig]:
        """Get configurations by value_type."""
        result = await db.execute(
            select(self.model)
            .where(self.model.value_type == value_type)
            .order_by(self.model.config_key)
        )
        return list(result.scalars().all())

    async def search_configs(self, db: AsyncSession, *, query: str) -> list[SystemConfig]:
        """Search configurations by key or description."""
        result = await db.execute(
            select(self.model)
            .where(
                self.model.config_key.ilike(f"%{query}%")
                | self.model.description.ilike(f"%{query}%")
            )
            .order_by(self.model.config_key)
        )
        return list(result.scalars().all())

    async def update_config_value(
        self,
        db: AsyncSession,
        *,
        config_key: str,
        config_value: JSONValue | str,
        updated_by: int | None = None,
        validate_enum: bool = True,
        allow_empty: bool = False,
        commit: bool = True,
    ) -> SystemConfig | None:
        """Update configuration value with validation by value_type/config_shape."""
        config = await self.get_by_key(db, config_key=config_key)
        if not config:
            logger.warning("system_config_update_not_found", config_key=config_key)
            return None

        normalized_value = self._normalize_config_value(
            config_key=config_key,
            value_type=ConfigValueType(config.value_type),
            config_shape=ConfigShape(config.config_shape),
            config_value=config_value,
            allowed_values=config.allowed_values,
            validate_enum=validate_enum,
            allow_empty=allow_empty,
        )
        config.config_value = normalized_value
        if updated_by is not None:
            config.updated_by = updated_by

        db.add(config)
        if commit:
            await db.commit()
            await db.refresh(config)
        else:
            await db.flush()

        logger.info("system_config_updated", config_key=config_key, updated_by=updated_by)
        return config

    async def batch_update_configs(
        self, db: AsyncSession, *, configs: dict[str, JSONValue], updated_by: int | None = None
    ) -> int:
        """Batch update multiple configurations."""
        count = 0
        for config_key, config_value in configs.items():
            updated = await self.update_config_value(
                db,
                config_key=config_key,
                config_value=config_value,
                updated_by=updated_by,
                validate_enum=True,
                commit=False,
            )
            if updated is not None:
                count += 1

        if count > 0:
            await db.commit()
        return count

    async def get_config_value(
        self, db: AsyncSession, *, config_key: str, default_value: JSONValue | None = None
    ) -> JSONValue | None:
        """Get parsed configuration value."""
        config = await self.get_by_key(db, config_key=config_key)
        if not config:
            return default_value

        value_type = ConfigValueType(config.value_type)
        config_shape = ConfigShape(config.config_shape)

        if config_shape == ConfigShape.ARRAY:
            if not isinstance(config.config_value, list):
                raise ValueError(
                    f"Invalid array configuration for '{config_key}': {config.config_value}"
                )

            normalized_items: list[JSONValue] = []
            for item in config.config_value:
                normalized_items.append(
                    self._normalize_stored_single_value(
                        config_key=config_key,
                        value_type=value_type,
                        value=item,
                    )
                )
            if len(normalized_items) == 0:
                raise ValueError(f"Invalid array configuration for '{config_key}': empty array")
            return cast(JSONValue, normalized_items)

        return self._normalize_stored_single_value(
            config_key=config_key,
            value_type=value_type,
            value=config.config_value,
        )


system_configs = CRUDSystemConfig(SystemConfig)
