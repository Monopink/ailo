"""
CRUD operations for LLM providers.

This module provides database operations for LLM providers.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.llm import LLMProvider
from app.schemas.llm import LLMProviderCreate, LLMProviderUpdate


class CRUDLLMProvider(CRUDBase[LLMProvider, LLMProviderCreate, LLMProviderUpdate]):
    """CRUD operations for LLMProvider model."""

    async def get_by_name(self, db: AsyncSession, *, name: str) -> LLMProvider | None:
        """Get LLM provider by name."""
        result = await db.execute(select(self.model).where(self.model.name == name))
        return result.scalar_one_or_none()


# Create instance
llm_provider = CRUDLLMProvider(LLMProvider)
