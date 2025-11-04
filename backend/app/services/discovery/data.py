"""
Discovery data layer.

This module handles complex queries for discovery page operations.
"""

from typing import List, Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai.template import AIProfileTemplate
from models.ai.character import AICharacter
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_random_templates(
    db: AsyncSession, user_qiao_id: str, count: int, category: Optional[str] = None
) -> List[AIProfileTemplate]:
    """
    Get random AI profile templates for square.

    Args:
        db: Database session
        user_qiao_id: Current user's qiao_id
        count: Number of templates to return
        category: Optional category filter

    Returns:
        List of random AIProfileTemplate objects
    """
    try:
        # 1) Find templates already used by this user (via character.request_params)
        result_used = await db.execute(
            select(AICharacter.request_params).where(AICharacter.user_qiao_id == user_qiao_id)
        )
        rows_used = result_used.scalars().all()
        used_template_qiao_ids = [
            params.get("created_from_profile_qiao_id")
            for params in rows_used
            if params and isinstance(params, dict) and params.get("created_from_profile_qiao_id")
        ]

        # 2) Main query: random active templates excluding those already used by this user
        query = select(AIProfileTemplate).where(
            and_(
                AIProfileTemplate.status == 1,  # active
                (
                    AIProfileTemplate.qiao_id.notin_(used_template_qiao_ids)
                    if used_template_qiao_ids
                    else True
                ),
            )
        )

        # Add category filter if provided
        if category is not None:
            query = query.where(AIProfileTemplate.category == category)

        # Random order and limit
        query = query.order_by(func.random()).limit(count)

        result = await db.execute(query)
        templates = list(result.scalars().all())

        logger.info(
            "random_templates_retrieved",
            user_qiao_id=user_qiao_id,
            count=len(templates),
            requested_count=count,
            category=category,
        )

        return templates

    except Exception as e:
        logger.error(
            "random_templates_query_failed",
            user_qiao_id=user_qiao_id,
            count=count,
            category=category,
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
