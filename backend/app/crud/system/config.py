"""System configuration CRUD operations.

This module contains CRUD operations for system configuration management.
"""

import json
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.enums import ConfigType
from app.models.system import SystemConfig
from app.schemas.system import SystemConfigCreate, SystemConfigUpdate
from app.services.config import config_service
from app.type_defs import JSONValue
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CRUDSystemConfig(CRUDBase[SystemConfig, SystemConfigCreate, SystemConfigUpdate]):
    """CRUD operations for SystemConfig model."""

    async def get_by_key(self, db: AsyncSession, *, config_key: str) -> SystemConfig | None:
        """Get configuration by key."""
        result = await db.execute(select(self.model).where(self.model.config_key == config_key))
        return result.scalar_one_or_none()

    async def get_by_type(self, db: AsyncSession, *, config_type: ConfigType) -> list[SystemConfig]:
        """Get configurations by type."""
        result = await db.execute(
            select(self.model)
            .where(self.model.config_type == config_type)
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
        config_value: str,
        updated_by: int | None = None,
        validate_enum: bool = True,
    ) -> SystemConfig | None:
        """Update configuration value with optional enum validation.

        Args:
            db: Database session
            config_key: Configuration key to update
            config_value: New configuration value
            updated_by: Admin user ID who is updating the config
            validate_enum: Whether to validate enum values (default: True)

        Returns:
            Updated SystemConfig object or None if not found

        Raises:
            ValueError: If enum validation fails or value is invalid

        """
        config = await self.get_by_key(db, config_key=config_key)
        if not config:
            logger.warning("system_config_update_not_found", config_key=config_key)
            return None

        # Enum validation (config_type=5)
        if validate_enum and config.config_type == ConfigType.ENUM:
            if config.allowed_values and config_value not in config.allowed_values:
                allowed_str = [str(v) for v in config.allowed_values]
                raise ValueError(
                    f"Invalid value '{config_value}' for {config_key}. "
                    f"Allowed values: {', '.join(allowed_str)}"
                )

        config.config_value = config_value
        if updated_by is not None:
            config.updated_by = updated_by

        db.add(config)
        await db.commit()
        await db.refresh(config)
        config_service.clear_cache(config_key)

        logger.info("system_config_updated", config_key=config_key, updated_by=updated_by)
        return config

    async def batch_update_configs(
        self, db: AsyncSession, *, configs: dict[str, JSONValue], updated_by: int | None = None
    ) -> int:
        """Batch update multiple configurations."""
        count = 0
        for config_key, config_value in configs.items():
            config = await self.get_by_key(db, config_key=config_key)
            if config:
                config.config_value = str(config_value)
                if updated_by:
                    config.updated_by = updated_by
                db.add(config)
                count += 1

        await db.commit()
        for config_key in configs:
            config_service.clear_cache(config_key)
        return count

    async def get_config_value(
        self, db: AsyncSession, *, config_key: str, default_value: JSONValue | None = None
    ) -> JSONValue | None:
        """Get parsed configuration value.

        Args:
            db: Database session
            config_key: Configuration key
            default_value: Default value if config not found

        Returns:
            Parsed configuration value or default_value if not found

        Raises:
            ValueError: If configuration value is invalid/corrupted

        """
        config = await self.get_by_key(db, config_key=config_key)
        if not config:
            return default_value

        # Parse value based on type
        if config.config_type == ConfigType.BOOLEAN:
            return config.config_value.lower() in ["true", "1"]
        if config.config_type == ConfigType.NUMBER:
            try:
                return float(config.config_value)
            except ValueError as e:
                logger.error(
                    "config_number_parse_error",
                    config_key=config_key,
                    config_value=config.config_value,
                    error=str(e),
                )
                raise ValueError(
                    f"Invalid number configuration for '{config_key}': {config.config_value}"
                )
        elif config.config_type == ConfigType.JSON:
            try:
                return cast(JSONValue, json.loads(config.config_value))
            except json.JSONDecodeError as e:
                logger.error(
                    "config_json_parse_error",
                    config_key=config_key,
                    config_value=config.config_value,
                    error=str(e),
                )
                raise ValueError(
                    f"Invalid JSON configuration for '{config_key}': {config.config_value}"
                )
        else:  # STRING
            return config.config_value


# Create instance
system_configs = CRUDSystemConfig(SystemConfig)
