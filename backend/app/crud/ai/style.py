"""
AI Style CRUD operations.

This module provides both standard CRUD operations and complex queries
for AI style and relationship mapping management.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud.base import CRUDBase
from models.ai import AIStyle, AIRelationship, AIRelationshipIndex
from schemas.ai import AIStyleCreate, AIStyleUpdate
from utils.logging import get_logger

logger = get_logger(__name__)


class CRUDAIStyle(CRUDBase[AIStyle, AIStyleCreate, AIStyleUpdate]):
    """AI Style CRUD operations with complex queries."""

    async def get_with_relationships(self, db: AsyncSession, *, style_id: int) -> Optional[Dict[str, Any]]:
        """
        Get style with its relationship mappings.

        Args:
            db: Database session
            style_id: Style ID

        Returns:
            Dictionary containing style and relationship mappings, or None if not found
        """
        try:
            # Get style
            style_result = await db.execute(select(AIStyle).where(AIStyle.id == style_id))
            style = style_result.scalar_one_or_none()

            if not style:
                logger.warning("style_not_found", style_id=style_id)
                return None

            # Get relationship indexes
            indexes_result = await db.execute(
                select(AIRelationshipIndex, AIRelationship)
                .join(AIRelationship, AIRelationshipIndex.relationship_id == AIRelationship.id)
                .where(AIRelationshipIndex.style_id == style_id)
                .order_by(AIRelationshipIndex.score_order, AIRelationshipIndex.priority)
            )

            indexes = indexes_result.all()

            relationship_mappings = []
            for index, relationship in indexes:
                relationship_mappings.append(
                    {
                        "score_order": index.score_order,
                        "score_name": index.score_name,
                        "start_position": index.start_position,
                        "end_position": index.end_position,
                        "relationship": relationship,
                        "priority": index.priority,
                        "limit_count": index.limit_count,
                    }
                )

            return {
                "style": style,
                "relationship_mappings": relationship_mappings,
            }

        except Exception as e:
            logger.error("style_with_relationships_query_failed", error=str(e), style_id=style_id)
            raise RuntimeError(f"Failed to get style with relationships: {str(e)}")

    async def get_relationship_mappings(self, db: AsyncSession, *, style_id: int) -> List[Dict[str, Any]]:
        """
        Get relationship mappings for a style.

        Args:
            db: Database session
            style_id: Style ID

        Returns:
            List of relationship mapping dictionaries
        """
        try:
            result = await db.execute(
                select(AIRelationshipIndex, AIRelationship)
                .join(AIRelationship, AIRelationshipIndex.relationship_id == AIRelationship.id)
                .where(AIRelationshipIndex.style_id == style_id)
                .order_by(AIRelationshipIndex.score_order, AIRelationshipIndex.priority)
            )

            indexes = result.all()

            mappings = []
            for index, relationship in indexes:
                mappings.append(
                    {
                        "index_id": index.id,
                        "score_order": index.score_order,
                        "score_name": index.score_name,
                        "start_position": index.start_position,
                        "end_position": index.end_position,
                        "priority": index.priority,
                        "limit_count": index.limit_count,
                        "relationship_id": relationship.id,
                        "relationship_name": relationship.name,
                        "relationship_prompt": relationship.prompt_fragment,
                    }
                )

            logger.debug("relationship_mappings_retrieved", style_id=style_id, count=len(mappings))

            return mappings

        except Exception as e:
            logger.error("relationship_mappings_query_failed", error=str(e), style_id=style_id)
            # Non-fatal error: return empty list
            return []

    async def get_available_styles(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[AIStyle]:
        """
        Get available styles for character creation.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of available styles
        """
        try:
            result = await db.execute(
                select(AIStyle)
                .where(AIStyle.status == 1)  # active
                .order_by(AIStyle.name)
                .offset(skip)
                .limit(limit)
            )

            styles = result.scalars().all()

            logger.debug("available_styles_retrieved", count=len(styles))

            return styles

        except Exception as e:
            logger.error("available_styles_query_failed", error=str(e))
            # Non-fatal error: return empty list
            return []

    async def get_score_ranges(self, db: AsyncSession, *, style_id: int) -> Dict[int, Dict[str, Any]]:
        """
        Get score ranges for a style.

        Args:
            db: Database session
            style_id: Style ID

        Returns:
            Dictionary mapping score_order to range info
        """
        try:
            style = await self.get(db, id=style_id)

            if not style:
                logger.warning("style_not_found_for_ranges", style_id=style_id)
                return {}

            # Extract score ranges from style configuration
            ranges = {}

            if style.score_name and isinstance(style.score_name, list):
                for i, score_name in enumerate(style.score_name):
                    ranges[i] = {
                        "name": score_name,
                        "start": 0,  # Default range
                        "end": 1000,
                    }

            logger.debug("score_ranges_retrieved", style_id=style_id, ranges_count=len(ranges))

            return ranges

        except Exception as e:
            logger.error("score_ranges_query_failed", error=str(e), style_id=style_id)
            return {}


class CRUDAIRelationship(CRUDBase[AIRelationship, Any, Any]):
    """AI Relationship CRUD operations."""

    async def get_by_name(self, db: AsyncSession, *, name: str) -> Optional[AIRelationship]:
        """
        Get relationship by name.

        Args:
            db: Database session
            name: Relationship name

        Returns:
            Relationship object or None if not found
        """
        try:
            result = await db.execute(select(AIRelationship).where(AIRelationship.name == name))
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("relationship_get_by_name_failed", error=str(e), name=name)
            return None

    async def get_available_relationships(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[AIRelationship]:
        """
        Get available relationships.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of available relationships
        """
        try:
            result = await db.execute(
                select(AIRelationship).order_by(AIRelationship.name).offset(skip).limit(limit)
            )

            relationships = result.scalars().all()

            logger.debug("available_relationships_retrieved", count=len(relationships))

            return relationships

        except Exception as e:
            logger.error("available_relationships_query_failed", error=str(e))
            # Non-fatal error: return empty list
            return []


class CRUDAIRelationshipIndex(CRUDBase[AIRelationshipIndex, Any, Any]):
    """AI Relationship Index CRUD operations."""

    async def get_by_style(self, db: AsyncSession, *, style_id: int) -> List[AIRelationshipIndex]:
        """
        Get relationship indexes by style ID.

        Args:
            db: Database session
            style_id: Style ID

        Returns:
            List of relationship indexes
        """
        try:
            result = await db.execute(
                select(AIRelationshipIndex)
                .where(AIRelationshipIndex.style_id == style_id)
                .order_by(AIRelationshipIndex.score_order, AIRelationshipIndex.priority)
            )

            indexes = result.scalars().all()

            logger.debug("relationship_indexes_retrieved", style_id=style_id, count=len(indexes))

            return indexes

        except Exception as e:
            logger.error("relationship_indexes_query_failed", error=str(e), style_id=style_id)
            # Non-fatal error: return empty list
            return []


ai_style = CRUDAIStyle(AIStyle)
ai_relationship = CRUDAIRelationship(AIRelationship)
ai_relationship_index = CRUDAIRelationshipIndex(AIRelationshipIndex)
