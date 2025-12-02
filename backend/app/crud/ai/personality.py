"""
AI Personality CRUD operations.

This module provides both standard CRUD operations and complex queries
for AI personality management.
"""

from typing import Any

from crud.base import CRUDBase
from models.ai import AIPersonality, AIPersonalityPlaceholder
from schemas.ai import AIPersonalityCreate, AIPersonalityUpdate
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

logger = get_logger(__name__)


class CRUDAIPersonality(CRUDBase[AIPersonality, AIPersonalityCreate, AIPersonalityUpdate]):
    """AI Personality CRUD operations with complex queries."""

    async def get_with_placeholders(
        self, db: AsyncSession, *, personality_id: int
    ) -> dict[str, Any] | None:
        """
        Get personality with its placeholders.

        Args:
            db: Database session
            personality_id: Personality ID

        Returns:
            Dictionary containing personality and placeholders, or None if not found
        """
        try:
            # Get personality
            personality_result = await db.execute(
                select(AIPersonality).where(AIPersonality.id == personality_id)
            )
            personality = personality_result.scalar_one_or_none()

            if not personality:
                logger.warning("personality_not_found", personality_id=personality_id)
                return None

            # Get placeholders (both specific and global)
            placeholders_result = await db.execute(
                select(AIPersonalityPlaceholder)
                .where(
                    or_(
                        AIPersonalityPlaceholder.personality_id == personality_id,
                        AIPersonalityPlaceholder.personality_id.is_(None),
                    )
                )
                .order_by(AIPersonalityPlaceholder.placeholder_key)
            )

            placeholders = placeholders_result.scalars().all()

            placeholder_dict = {}
            for placeholder in placeholders:
                placeholder_dict[placeholder.placeholder_key] = {
                    "display_name": placeholder.display_name,
                    "description": placeholder.description,
                    "example_value": placeholder.example_value,
                    "is_required": placeholder.is_required,
                }

            return {
                "personality": personality,
                "placeholders": placeholder_dict,
            }

        except Exception as e:
            logger.error(
                "personality_with_placeholders_query_failed",
                error=str(e),
                personality_id=personality_id,
            )
            raise RuntimeError(f"Failed to get personality with placeholders: {e!s}")

    async def get_available_personalities(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> list[AIPersonality]:
        """
        Get available personalities for instance creation.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of available personalities
        """
        try:
            result = await db.execute(
                select(AIPersonality)
                .where(AIPersonality.status == 1)  # active
                .order_by(AIPersonality.display_name)
                .offset(skip)
                .limit(limit)
            )

            personalities = list(result.scalars().all())

            logger.debug("available_personalities_retrieved", count=len(personalities))

            return personalities

        except Exception as e:
            logger.error("available_personalities_query_failed", error=str(e))
            # Non-fatal error: return empty list
            return []

    async def search_personalities(
        self, db: AsyncSession, *, query: str, skip: int = 0, limit: int = 20
    ) -> list[AIPersonality]:
        """
        Search personalities by display name or prompt text.

        Args:
            db: Database session
            query: Search query
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching personalities
        """
        try:
            search_pattern = f"%{query}%"

            result = await db.execute(
                select(AIPersonality)
                .where(
                    or_(
                        AIPersonality.display_name.ilike(search_pattern),
                        AIPersonality.prompt.ilike(search_pattern),
                    )
                )
                .where(AIPersonality.status == 1)  # active only
                .order_by(AIPersonality.display_name)
                .offset(skip)
                .limit(limit)
            )

            personalities = list(result.scalars().all())

            logger.debug("personalities_search_completed", query=query, count=len(personalities))

            return personalities

        except Exception as e:
            logger.error("personalities_search_failed", error=str(e), query=query)
            # Non-fatal error: return empty list
            return []


class CRUDAIPersonalityPlaceholder(CRUDBase[AIPersonalityPlaceholder, Any, Any]):
    """AI Personality Placeholder CRUD operations."""

    async def get_by_personality(
        self, db: AsyncSession, *, personality_id: int | None = None
    ) -> list[AIPersonalityPlaceholder]:
        """
        Get placeholders by personality ID (or global placeholders if None).

        Args:
            db: Database session
            personality_id: Personality ID, or None for global placeholders

        Returns:
            List of placeholders
        """
        try:
            if personality_id is None:
                # Get global placeholders
                result = await db.execute(
                    select(AIPersonalityPlaceholder)
                    .where(AIPersonalityPlaceholder.personality_id.is_(None))
                    .order_by(AIPersonalityPlaceholder.placeholder_key)
                )
            else:
                # Get personality-specific placeholders
                result = await db.execute(
                    select(AIPersonalityPlaceholder)
                    .where(AIPersonalityPlaceholder.personality_id == personality_id)
                    .order_by(AIPersonalityPlaceholder.placeholder_key)
                )

            placeholders = list(result.scalars().all())

            logger.debug(
                "placeholders_retrieved", personality_id=personality_id, count=len(placeholders)
            )

            return placeholders

        except Exception as e:
            logger.error("placeholders_query_failed", error=str(e), personality_id=personality_id)
            # Non-fatal error: return empty list
            return []

    async def get_by_key(
        self, db: AsyncSession, *, placeholder_key: str, personality_id: int | None = None
    ) -> AIPersonalityPlaceholder | None:
        """
        Get placeholder by key and personality ID.

        Args:
            db: Database session
            placeholder_key: Placeholder key
            personality_id: Personality ID, or None for global placeholder

        Returns:
            Placeholder object or None if not found
        """
        try:
            result = await db.execute(
                select(AIPersonalityPlaceholder).where(
                    AIPersonalityPlaceholder.placeholder_key == placeholder_key,
                    AIPersonalityPlaceholder.personality_id == personality_id,
                )
            )

            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(
                "placeholder_get_by_key_failed",
                error=str(e),
                placeholder_key=placeholder_key,
                personality_id=personality_id,
            )
            return None

    async def get_placeholders_by_personality(
        self, db: AsyncSession, *, personality_id: int
    ) -> list[AIPersonalityPlaceholder]:
        """
        Get all placeholders for a personality (both specific and global).

        Args:
            db: Database session
            personality_id: Personality ID

        Returns:
            List of placeholders (personality-specific + global)
        """
        try:
            result = await db.execute(
                select(AIPersonalityPlaceholder)
                .where(
                    or_(
                        AIPersonalityPlaceholder.personality_id == personality_id,
                        AIPersonalityPlaceholder.personality_id.is_(None),
                    )
                )
                .order_by(AIPersonalityPlaceholder.placeholder_key)
            )

            placeholders = list(result.scalars().all())

            logger.debug(
                "placeholders_by_personality_retrieved",
                personality_id=personality_id,
                count=len(placeholders),
            )

            return placeholders

        except Exception as e:
            logger.error(
                "placeholders_by_personality_query_failed",
                error=str(e),
                personality_id=personality_id,
            )
            return []


ai_personality = CRUDAIPersonality(AIPersonality)
ai_personality_placeholder = CRUDAIPersonalityPlaceholder(AIPersonalityPlaceholder)
