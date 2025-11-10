"""
Discovery data layer.

This module handles complex queries for discovery page operations.
"""

from typing import List, Optional, Tuple
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai.template import AIProfileTemplate
from models.ai.character import AICharacter
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_random_templates(
    db: AsyncSession,
    user_qiao_id: str,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[AIProfileTemplate], int]:
    """
    Get random AI profile templates with pagination.

    Args:
        db: Database session
        user_qiao_id: Current user's qiao_id
        category: Optional category filter
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (templates list, total count)
    """
    try:
        # Build subquery for excluded templates (optimized)
        excluded_subquery = (
            select(AICharacter.created_from_profile_qiao_id)
            .where(
                and_(
                    AICharacter.user_qiao_id == user_qiao_id,
                    AICharacter.created_from_profile_qiao_id.isnot(None),
                )
            )
            .scalar_subquery()
        )

        # Build base query
        base_conditions = [AIProfileTemplate.status == 1]

        if category is not None:
            base_conditions.append(AIProfileTemplate.category == category)

        # Count query
        count_query = select(func.count()).select_from(AIProfileTemplate).where(
            and_(
                *base_conditions,
                AIProfileTemplate.qiao_id.notin_(excluded_subquery),
            )
        )
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Data query with pagination
        offset = (page - 1) * page_size
        data_query = (
            select(AIProfileTemplate)
            .where(
                and_(
                    *base_conditions,
                    AIProfileTemplate.qiao_id.notin_(excluded_subquery),
                )
            )
            .order_by(func.random())
            .offset(offset)
            .limit(page_size)
        )

        result = await db.execute(data_query)
        templates = list(result.scalars().all())

        logger.info(
            "random_templates_retrieved",
            user_qiao_id=user_qiao_id,
            count=len(templates),
            total=total,
            category=category,
            page=page,
        )

        return templates, total

    except Exception as e:
        logger.error(
            "random_templates_query_failed",
            user_qiao_id=user_qiao_id,
            category=category,
            page=page,
            error=str(e),
        )
        raise


async def get_template_by_qiao_id(db: AsyncSession, qiao_id: str) -> Optional[AIProfileTemplate]:
    """
    Get AI profile template by qiao_id.

    Args:
        db: Database session
        qiao_id: Template qiao_id

    Returns:
        AIProfileTemplate or None if not found
    """
    try:
        query = select(AIProfileTemplate).where(
            and_(AIProfileTemplate.qiao_id == qiao_id, AIProfileTemplate.status == 1)  # active only
        )

        result = await db.execute(query)
        template = result.scalar_one_or_none()

        if template:
            logger.debug("template_found", qiao_id=qiao_id)
        else:
            logger.debug("template_not_found", qiao_id=qiao_id)

        return template

    except Exception as e:
        logger.error("template_query_failed", qiao_id=qiao_id, error=str(e))
        raise
