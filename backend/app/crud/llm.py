"""
LLM provider and configuration CRUD operations.

This module contains CRUD operations for LLM management.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import selectinload

from models.llm import LLMProvider, LLMConfig
from schemas.llm import LLMProviderCreate, LLMProviderUpdate, LLMConfigCreate, LLMConfigUpdate
from .base import CRUDBase


class CRUDLLMProvider(CRUDBase[LLMProvider, LLMProviderCreate, LLMProviderUpdate]):
    """CRUD operations for LLMProvider model."""

    async def get_by_name(self, db: AsyncSession, *, name: str) -> Optional[LLMProvider]:
        """Get LLM provider by name."""
        result = await db.execute(select(self.model).where(self.model.name == name))
        return result.scalar_one_or_none()

    async def get_active_providers(self, db: AsyncSession) -> List[LLMProvider]:
        """Get all active LLM providers."""
        result = await db.execute(
            select(self.model).where(self.model.status == 1).order_by(self.model.name)
        )
        return list(result.scalars().all())

    async def update_status(
        self, db: AsyncSession, *, provider_id: int, status: int
    ) -> Optional[LLMProvider]:
        """Update provider status."""
        provider = await self.get(db, id=provider_id)
        if provider:
            provider.status = status
            await db.commit()
            await db.refresh(provider)
        return provider


class CRUDLLMConfig(CRUDBase[LLMConfig, LLMConfigCreate, LLMConfigUpdate]):
    """CRUD operations for LLMConfig model."""

    async def get_by_config_key(self, db: AsyncSession, *, config_key: str) -> Optional[LLMConfig]:
        """Get LLM config by config key."""
        result = await db.execute(select(self.model).where(self.model.config_key == config_key))
        return result.scalar_one_or_none()

    async def get_by_provider(
        self, db: AsyncSession, *, provider_id: int, skip: int = 0, limit: int = 100
    ) -> List[LLMConfig]:
        """Get configs by provider ID."""
        result = await db.execute(
            select(self.model)
            .where(self.model.provider_id == provider_id)
            .order_by(self.model.priority, self.model.config_key)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_configs(
        self, db: AsyncSession, provider_id: Optional[int] = None
    ) -> List[LLMConfig]:
        """Get all active configs, optionally filtered by provider."""
        conditions = [self.model.is_active == 1]
        if provider_id:
            conditions.append(self.model.provider_id == provider_id)

        result = await db.execute(
            select(self.model).where(and_(*conditions)).order_by(self.model.priority, self.model.config_key)
        )
        return list(result.scalars().all())

    async def get_primary_config(self, db: AsyncSession) -> Optional[LLMConfig]:
        """Get the primary (highest priority active) config."""
        result = await db.execute(
            select(self.model).where(self.model.is_active == 1).order_by(self.model.priority).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_config_with_provider(self, db: AsyncSession, *, config_id: int) -> Optional[LLMConfig]:
        """Get config with provider information."""
        result = await db.execute(
            select(self.model).options(selectinload(self.model.provider)).where(self.model.id == config_id)
        )
        return result.scalar_one_or_none()

    async def update_active_status(
        self, db: AsyncSession, *, config_id: int, is_active: bool
    ) -> Optional[LLMConfig]:
        """Update config active status."""
        config = await self.get(db, id=config_id)
        if config:
            config.is_active = is_active
            await db.commit()
            await db.refresh(config)
        return config

    async def get_configs_by_priority(self, db: AsyncSession, active_only: bool = True) -> List[LLMConfig]:
        """Get configs ordered by priority."""
        conditions = []
        if active_only:
            conditions.append(self.model.is_active == 1)

        query = select(self.model).order_by(self.model.priority, self.model.config_key)
        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        return list(result.scalars().all())


# Create instances
llm_provider = CRUDLLMProvider(LLMProvider)
llm_config = CRUDLLMConfig(LLMConfig)
