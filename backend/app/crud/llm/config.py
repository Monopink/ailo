"""CRUD operations for LLM configurations.

This module provides database operations for LLM configurations.
"""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.llm import LLMConfig
from app.schemas.llm import LLMConfigCreate, LLMConfigUpdate


class CRUDLLMConfig(CRUDBase[LLMConfig, LLMConfigCreate, LLMConfigUpdate]):
    """CRUD operations for LLMConfig model."""

    async def get_by_name(self, db: AsyncSession, *, name: str) -> LLMConfig | None:
        """Get LLM config by name."""
        result = await db.execute(select(self.model).where(self.model.name == name))
        return result.scalar_one_or_none()

    async def get_by_provider(
        self, db: AsyncSession, *, provider_id: int, skip: int = 0, limit: int = 100
    ) -> list[LLMConfig]:
        """Get configs by provider ID."""
        result = await db.execute(
            select(self.model)
            .where(self.model.provider_id == provider_id)
            .order_by(self.model.priority, self.model.name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_configs(
        self, db: AsyncSession, provider_id: int | None = None
    ) -> list[LLMConfig]:
        """Get all active configs, optionally filtered by provider."""
        conditions = [self.model.status == 1]
        if provider_id:
            conditions.append(self.model.provider_id == provider_id)

        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(self.model.priority, self.model.name)
        )
        return list(result.scalars().all())

    async def get_primary_config(self, db: AsyncSession) -> LLMConfig | None:
        """Get the primary (highest priority active) config."""
        result = await db.execute(
            select(self.model).where(self.model.status == 1).order_by(self.model.priority).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_config_with_provider(
        self, db: AsyncSession, *, config_id: int
    ) -> LLMConfig | None:
        """Get config with provider information."""
        result = await db.execute(
            select(self.model)
            .options(selectinload(self.model.provider))
            .where(self.model.id == config_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, db: AsyncSession, *, config_id: int, status: int
    ) -> LLMConfig | None:
        """Update config status."""
        config = await self.get(db, record_id=config_id)
        if config:
            config.status = status
            await db.commit()
            await db.refresh(config)
        return config

    async def get_configs_by_priority(
        self, db: AsyncSession, active_only: bool = True
    ) -> list[LLMConfig]:
        """Get configs ordered by priority."""
        conditions = []
        if active_only:
            conditions.append(self.model.status == 1)

        query = select(self.model).order_by(self.model.priority, self.model.name)
        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        return list(result.scalars().all())


# Create instance
llm_config = CRUDLLMConfig(LLMConfig)
