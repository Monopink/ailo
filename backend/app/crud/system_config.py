from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models.system_config import SystemConfig
from utils.logging import get_logger, bind_context
from .base import CRUDBase

logger = get_logger(__name__)


class CRUDSystemConfig(CRUDBase[SystemConfig]):
    """CRUD operations for SystemConfig."""

    async def get_by_key(self, db: AsyncSession, config_key: str) -> Optional[SystemConfig]:
        """Get system config by key."""
        try:
            op_logger = bind_context(logger, operation="get_config_by_key", config_key=config_key)
            op_logger.info("fetching_config_by_key")

            result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == config_key))
            config = result.scalar_one_or_none()

            if config:
                op_logger.info("config_found")
            else:
                op_logger.info("config_not_found")

            return config

        except Exception as e:
            logger.error("get_config_by_key_error", error=str(e), config_key=config_key)
            raise

    async def set_config(
        self, db: AsyncSession, config_key: str, config_value: str, description: Optional[str] = None
    ) -> SystemConfig:
        """Set or update system configuration."""
        try:
            op_logger = bind_context(logger, operation="set_config", config_key=config_key)
            op_logger.info("setting_config")

            # Check if config exists
            existing_config = await self.get_by_key(db, config_key)

            if existing_config:
                # Update existing config
                await db.execute(
                    update(SystemConfig)
                    .where(SystemConfig.config_key == config_key)
                    .values(config_value=config_value, description=description)
                )
                await db.commit()

                # Refresh to get updated data
                await db.refresh(existing_config)
                op_logger.info("config_updated")
                return existing_config
            else:
                # Create new config
                config_data = {
                    "config_key": config_key,
                    "config_value": config_value,
                    "description": description,
                }
                new_config = await self.create(db, obj_in=config_data)
                op_logger.info("config_created")
                return new_config

        except Exception as e:
            await db.rollback()
            logger.error("set_config_error", error=str(e), config_key=config_key)
            raise

    async def get_config_value(
        self, db: AsyncSession, config_key: str, default_value: Optional[str] = None
    ) -> Optional[str]:
        """Get configuration value by key, return default if not found."""
        try:
            config = await self.get_by_key(db, config_key)
            if config:
                return config.config_value
            return default_value

        except Exception as e:
            logger.error("get_config_value_error", error=str(e), config_key=config_key)
            return default_value

    async def delete_config(self, db: AsyncSession, config_key: str) -> bool:
        """Delete configuration by key."""
        try:
            op_logger = bind_context(logger, operation="delete_config", config_key=config_key)
            op_logger.info("deleting_config")

            config = await self.get_by_key(db, config_key)
            if config:
                await db.delete(config)
                await db.commit()
                op_logger.info("config_deleted")
                return True
            else:
                op_logger.info("config_not_found_for_deletion")
                return False

        except Exception as e:
            await db.rollback()
            logger.error("delete_config_error", error=str(e), config_key=config_key)
            raise


# Create instance
system_config_crud = CRUDSystemConfig(SystemConfig)
