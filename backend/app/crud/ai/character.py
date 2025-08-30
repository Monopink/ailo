"""
AI Character CRUD operations.

This module provides both standard CRUD operations and complex queries
for AI character management.
"""

from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.ai import AICharacter
from schemas.ai import AICharacterCreate, AICharacterUpdate
from utils.logging import get_logger

logger = get_logger(__name__)


class CRUDAICharacter(CRUDBase[AICharacter, AICharacterCreate, AICharacterUpdate]):
    """AI Character CRUD operations with complex queries."""

    async def get_by_qiao_id(self, db: AsyncSession, *, qiao_id: str) -> Optional[AICharacter]:
        """
        Get character by qiao_id.

        Args:
            db: Database session
            qiao_id: Character's qiao_id

        Returns:
            Character object or None if not found
        """
        try:
            result = await db.execute(select(AICharacter).where(AICharacter.qiao_id == qiao_id))
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("character_get_by_qiao_id_failed", error=str(e), qiao_id=qiao_id)
            raise RuntimeError(f"Failed to get character by qiao_id: {str(e)}")

    # Complex queries moved to services/ai/data layer for better separation of concerns

    async def get_user_characters(
        self, db: AsyncSession, *, user_qiao_id: str, skip: int = 0, limit: int = 100
    ) -> List[AICharacter]:
        """
        Get characters created by a specific user.

        Args:
            db: Database session
            user_qiao_id: User's qiao_id
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of characters
        """
        try:
            result = await db.execute(
                select(AICharacter)
                .where(AICharacter.user_qiao_id == user_qiao_id)
                .order_by(desc(AICharacter.created_at))
                .offset(skip)
                .limit(limit)
            )

            characters = result.scalars().all()

            logger.debug("user_characters_retrieved", user_qiao_id=user_qiao_id, count=len(characters))

            return characters

        except Exception as e:
            logger.error("user_characters_query_failed", error=str(e), user_qiao_id=user_qiao_id)
            # Non-fatal error: return empty list
            return []


ai_character = CRUDAICharacter(AICharacter)
