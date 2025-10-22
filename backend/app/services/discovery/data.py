"""
Discovery data layer.

This module handles complex queries for discovery page operations.
"""

from typing import List, Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai.template import AIProfileTemplate
from models.contact import Contact
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_random_templates(
    db: AsyncSession,
    user_qiao_id: str,
    count: int,
    category: Optional[str] = None
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
        # Subquery: get contact_qiao_ids already added by user
        added_contacts_subquery = (
            select(Contact.contact_qiao_id)
            .where(
                and_(
                    Contact.user_qiao_id == user_qiao_id,
                    Contact.deleted_at.is_(None)
                )
            )
        )

        # Main query: get random templates
        query = select(AIProfileTemplate).where(
            and_(
                AIProfileTemplate.status == 1,  # active
                AIProfileTemplate.is_reusable == 1,  # public/reusable
                AIProfileTemplate.qiao_id.notin_(added_contacts_subquery)
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
            category=category
        )

        return templates

    except Exception as e:
        logger.error(
            "random_templates_query_failed",
            user_qiao_id=user_qiao_id,
            count=count,
            category=category,
            error=str(e)
        )
        raise

