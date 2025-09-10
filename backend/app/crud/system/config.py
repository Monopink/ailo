"""
System configuration CRUD operations.

This module contains CRUD operations for system configuration management.
"""

from typing import List, Optional, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.system import SystemConfig
from schemas.system import SystemConfigCreate, SystemConfigUpdate
from enums import ConfigType
from utils.logging import get_logger

logger = get_logger(__name__)


class CRUDSystemConfig(CRUDBase[SystemConfig, SystemConfigCreate, SystemConfigUpdate]):
    """CRUD operations for SystemConfig model."""

    async def get_by_key(self, db: AsyncSession, *, config_key: str) -> Optional[SystemConfig]:
        """Get configuration by key."""
        result = await db.execute(select(self.model).where(self.model.config_key == config_key))
        return result.scalar_one_or_none()

    async def get_public_configs(self, db: AsyncSession) -> List[SystemConfig]:
        """Get all public configurations."""
        result = await db.execute(
            select(self.model).where(self.model.is_public == 1).order_by(self.model.config_key)
        )
        return list(result.scalars().all())

    async def get_by_type(self, db: AsyncSession, *, config_type: ConfigType) -> List[SystemConfig]:
        """Get configurations by type."""
        result = await db.execute(
            select(self.model).where(self.model.config_type == config_type).order_by(self.model.config_key)
        )
        return list(result.scalars().all())

    async def search_configs(
        self, db: AsyncSession, *, query: str, include_private: bool = False
    ) -> List[SystemConfig]:
        """Search configurations by key or description."""
        conditions = [
            self.model.config_key.ilike(f"%{query}%") | self.model.description.ilike(f"%{query}%")
        ]

        if not include_private:
            conditions.append(self.model.is_public == 1)

        result = await db.execute(
            select(self.model).where(and_(*conditions)).order_by(self.model.config_key)
        )
        return list(result.scalars().all())

    async def update_config_value(
        self, db: AsyncSession, *, config_key: str, config_value: str, updated_by: Optional[int] = None
    ) -> Optional[SystemConfig]:
        """Update configuration value."""
        config = await self.get_by_key(db, config_key=config_key)
        if config:
            config.config_value = config_value
            if updated_by:
                config.updated_by = updated_by
            db.add(config)
            await db.commit()
            await db.refresh(config)
        return config

    async def batch_update_configs(
        self, db: AsyncSession, *, configs: dict, updated_by: Optional[int] = None
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
        return count

    async def get_config_value(
        self, db: AsyncSession, *, config_key: str, default_value: Any = None
    ) -> Any:
        """
        Get parsed configuration value.

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
        elif config.config_type == ConfigType.NUMBER:
            try:
                return float(config.config_value)
            except ValueError as e:
                logger.error(
                    "config_number_parse_error",
                    config_key=config_key,
                    config_value=config.config_value,
                    error=str(e),
                )
                raise ValueError(f"Invalid number configuration for '{config_key}': {config.config_value}")
        elif config.config_type == ConfigType.JSON:
            import json

            try:
                return json.loads(config.config_value)
            except json.JSONDecodeError as e:
                logger.error(
                    "config_json_parse_error",
                    config_key=config_key,
                    config_value=config.config_value,
                    error=str(e),
                )
                raise ValueError(f"Invalid JSON configuration for '{config_key}': {config.config_value}")
        else:  # STRING
            return config.config_value


# Create instance
system_configs = CRUDSystemConfig(SystemConfig)
