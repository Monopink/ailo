"""
AI Style CRUD operations.

This module provides both standard CRUD operations and complex queries
for AI style and relationship mapping management.
"""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.ai import (
    AIDimension,
    AIDimensionRelationshipMapping,
    AIRelationship,
    AIStyle,
    AIStyleDimension,
)
from app.schemas.ai import (
    AIRelationshipResponse,
    AIStyleCreate,
    AIStyleDimensionCreate,
    AIStyleDimensionUpdate,
    AIStyleResponse,
    AIStyleUpdate,
    DimensionScoreRange,
    RelationshipMappingDetail,
    RelationshipMappingWithDimension,
    StyleWithRelationships,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


# Dummy schemas for read-only CRUD operations
class _ReadOnlySchema(BaseModel):
    """
    Dummy schema for read-only CRUD operations.

    AIRelationship and AIDimensionRelationshipMapping tables are managed
    through admin interface, so create/update operations are not used in code.
    """


class CRUDAIStyle(CRUDBase[AIStyle, AIStyleCreate, AIStyleUpdate]):
    """AI Style CRUD operations with complex queries."""

    async def get_with_relationships(
        self, db: AsyncSession, *, style_id: int
    ) -> StyleWithRelationships | None:
        """
        Get style with its relationship mappings.

        Args:
            db: Database session
            style_id: Style ID

        Returns:
            StyleWithRelationships object or None if not found
        """
        try:
            # Get style
            style_result = await db.execute(select(AIStyle).where(AIStyle.id == style_id))
            style = style_result.scalar_one_or_none()

            if not style:
                logger.warning("style_not_found", style_id=style_id)
                return None

            # Get relationship mappings with dimension info (normalized schema)
            mappings_result = await db.execute(
                select(AIDimensionRelationshipMapping, AIRelationship, AIDimension)
                .join(
                    AIRelationship,
                    AIDimensionRelationshipMapping.relationship_id == AIRelationship.id,
                )
                .join(AIDimension, AIDimensionRelationshipMapping.dimension_id == AIDimension.id)
                .join(
                    AIStyleDimension,
                    AIStyleDimension.dimension_id == AIDimensionRelationshipMapping.dimension_id,
                )
                .where(AIStyleDimension.style_id == style_id)
                .order_by(AIDimension.name, AIDimensionRelationshipMapping.priority)
            )

            rows = mappings_result.all()

            relationship_mappings: list[RelationshipMappingWithDimension] = []
            for mapping, relationship, dimension in rows:
                relationship_mappings.append(
                    RelationshipMappingWithDimension(
                        dimension_id=mapping.dimension_id,
                        dimension_name=dimension.name,
                        start_position=mapping.start_position,
                        end_position=mapping.end_position,
                        priority=mapping.priority,
                        limit_count=mapping.limit_count,
                        relationship=AIRelationshipResponse(
                            display_name=relationship.display_name,
                            prompt_fragment=relationship.prompt_fragment,
                            status=relationship.status,
                            created_at=relationship.created_at,
                            updated_at=relationship.updated_at,
                        ),
                    )
                )

            return StyleWithRelationships(
                style=AIStyleResponse(
                    id=style.id,
                    display_name=style.display_name,
                    status=style.status,
                    created_at=style.created_at,
                    updated_at=style.updated_at,
                ),
                relationship_mappings=relationship_mappings,
            )

        except Exception as e:
            logger.error("style_with_relationships_query_failed", error=str(e), style_id=style_id)
            raise RuntimeError(f"Failed to get style with relationships: {e!s}")

    async def get_relationship_mappings(
        self, db: AsyncSession, *, style_id: int
    ) -> list[RelationshipMappingDetail]:
        """
        Get relationship mappings for a style.

        Args:
            db: Database session
            style_id: Style ID

        Returns:
            List of relationship mapping details
        """
        try:
            result = await db.execute(
                select(AIDimensionRelationshipMapping, AIRelationship, AIDimension)
                .join(
                    AIRelationship,
                    AIDimensionRelationshipMapping.relationship_id == AIRelationship.id,
                )
                .join(AIDimension, AIDimensionRelationshipMapping.dimension_id == AIDimension.id)
                .join(
                    AIStyleDimension,
                    AIStyleDimension.dimension_id == AIDimensionRelationshipMapping.dimension_id,
                )
                .where(AIStyleDimension.style_id == style_id)
                .order_by(AIDimension.name, AIDimensionRelationshipMapping.priority)
            )

            rows = result.all()

            mappings: list[RelationshipMappingDetail] = []
            for mapping, relationship, dimension in rows:
                mappings.append(
                    RelationshipMappingDetail(
                        mapping_id=mapping.id,
                        dimension_id=mapping.dimension_id,
                        dimension_name=dimension.name,
                        start_position=mapping.start_position,
                        end_position=mapping.end_position,
                        priority=mapping.priority,
                        limit_count=mapping.limit_count,
                        relationship_id=relationship.id,
                        relationship_display_name=relationship.display_name,
                        relationship_prompt=relationship.prompt_fragment,
                    )
                )

            logger.debug("relationship_mappings_retrieved", style_id=style_id, count=len(mappings))

            return mappings

        except Exception as e:
            logger.error("relationship_mappings_query_failed", error=str(e), style_id=style_id)
            # Non-fatal error: return empty list
            return []

    async def get_available_styles(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> list[AIStyle]:
        """
        Get available styles for instance creation.

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
                .order_by(AIStyle.display_name)
                .offset(skip)
                .limit(limit)
            )

            styles = list(result.scalars().all())

            logger.debug("available_styles_retrieved", count=len(styles))

            return styles

        except Exception as e:
            logger.error("available_styles_query_failed", error=str(e))
            # Non-fatal error: return empty list
            return []

    async def get_score_ranges(
        self, db: AsyncSession, *, style_id: int
    ) -> dict[str, DimensionScoreRange]:
        """
        Get score ranges for a style.

        Args:
            db: Database session
            style_id: Style ID

        Returns:
            Dictionary mapping dimension name to range info
        """
        try:
            style = await self.get(db, id=style_id)

            if not style:
                logger.warning("style_not_found_for_ranges", style_id=style_id)
                return {}

            # Get dimensions for the style with dimension info
            dimensions_result = await db.execute(
                select(AIStyleDimension, AIDimension)
                .join(AIDimension, AIDimension.id == AIStyleDimension.dimension_id)
                .where(AIStyleDimension.style_id == style_id)
            )
            dimensions = dimensions_result.all()

            ranges: dict[str, DimensionScoreRange] = {}
            for style_dimension, dimension in dimensions:
                ranges[dimension.name] = DimensionScoreRange(
                    name=dimension.name,
                    display_name=dimension.display_name,
                    initial_position=style_dimension.initial_position,
                    start=0,  # Full range
                    end=1000,
                )

            logger.debug("score_ranges_retrieved", style_id=style_id, ranges_count=len(ranges))

            return ranges

        except Exception as e:
            logger.error("score_ranges_query_failed", error=str(e), style_id=style_id)
            return {}


class CRUDAIRelationship(CRUDBase[AIRelationship, _ReadOnlySchema, _ReadOnlySchema]):
    """AI Relationship CRUD operations."""

    async def get_available_relationships(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> list[AIRelationship]:
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
                select(AIRelationship)
                .order_by(AIRelationship.display_name)
                .offset(skip)
                .limit(limit)
            )

            relationships = list(result.scalars().all())

            logger.debug("available_relationships_retrieved", count=len(relationships))

            return relationships

        except Exception as e:
            logger.error("available_relationships_query_failed", error=str(e))
            # Non-fatal error: return empty list
            return []


class CRUDAIDimensionRelationshipMapping(
    CRUDBase[AIDimensionRelationshipMapping, _ReadOnlySchema, _ReadOnlySchema]
):
    """AI Dimension Relationship Mapping CRUD operations (normalized)."""

    async def get_by_style(
        self, db: AsyncSession, *, style_id: int
    ) -> list[AIDimensionRelationshipMapping]:
        """
        Get dimension relationship mappings by style ID.

        Args:
            db: Database session
            style_id: Style ID

        Returns:
            List of dimension relationship mappings
        """
        try:
            result = await db.execute(
                select(AIDimensionRelationshipMapping)
                .join(
                    AIStyleDimension,
                    AIStyleDimension.dimension_id == AIDimensionRelationshipMapping.dimension_id,
                )
                .where(AIStyleDimension.style_id == style_id)
                .order_by(AIDimensionRelationshipMapping.priority.desc())
            )

            mappings = list(result.scalars().all())

            logger.debug(
                "dimension_relationship_mappings_retrieved", style_id=style_id, count=len(mappings)
            )

            return mappings

        except Exception as e:
            logger.error(
                "dimension_relationship_mappings_query_failed", error=str(e), style_id=style_id
            )
            # Non-fatal error: return empty list
            return []


class CRUDAIStyleDimension(
    CRUDBase[AIStyleDimension, AIStyleDimensionCreate, AIStyleDimensionUpdate]
):
    """AI Style Dimension CRUD operations."""

    async def get_by_style_and_name(
        self, db: AsyncSession, *, style_id: int, name: str
    ) -> AIStyleDimension | None:
        """
        Get dimension by style ID and name.

        Args:
            db: Database session
            style_id: Style ID
            name: Dimension name

        Returns:
            Dimension object or None if not found
        """
        try:
            result = await db.execute(
                select(AIStyleDimension)
                .join(AIDimension, AIDimension.id == AIStyleDimension.dimension_id)
                .where(AIStyleDimension.style_id == style_id)
                .where(AIDimension.name == name)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(
                "dimension_get_by_style_name_failed", error=str(e), style_id=style_id, name=name
            )
            return None

    async def get_by_style(self, db: AsyncSession, *, style_id: int) -> list[AIStyleDimension]:
        """
        Get all dimensions for a style.

        Args:
            db: Database session
            style_id: Style ID

        Returns:
            List of dimension objects
        """
        try:
            result = await db.execute(
                select(AIStyleDimension)
                .join(AIDimension, AIDimension.id == AIStyleDimension.dimension_id)
                .where(AIStyleDimension.style_id == style_id)
                .order_by(AIDimension.name)
            )
            dimensions = result.scalars().all()

            logger.debug("dimensions_retrieved", style_id=style_id, count=len(dimensions))
            return list(dimensions)

        except Exception as e:
            logger.error("dimensions_query_failed", error=str(e), style_id=style_id)
            return []


ai_style = CRUDAIStyle(AIStyle)
ai_relationship = CRUDAIRelationship(AIRelationship)
ai_dimension_relationship_mapping = CRUDAIDimensionRelationshipMapping(
    AIDimensionRelationshipMapping
)
ai_style_dimension = CRUDAIStyleDimension(AIStyleDimension)
