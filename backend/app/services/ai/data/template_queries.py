"""
AI template-related query functions.

This module provides template-related read/query functions with clear
separation of concerns and pure function design.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.ai.template import AIProfileTemplate, AIInfoTemplate
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_profile_template_with_info(
    db: AsyncSession, profile_template_id: int
) -> Optional[Dict[str, Any]]:
    """
    Get profile template with associated info template.

    Args:
        db: Database session
        profile_template_id: Profile template ID

    Returns:
        Dictionary containing profile template and info template, or None if not found
    """
    try:
        # Get profile template
        profile_result = await db.execute(
            select(AIProfileTemplate).where(AIProfileTemplate.id == profile_template_id)
        )
        profile_template = profile_result.scalar_one_or_none()

        if not profile_template:
            logger.warning("profile_template_not_found", profile_template_id=profile_template_id)
            return None

        # Get associated info template
        info_template = None
        if profile_template.info_id:
            info_result = await db.execute(
                select(AIInfoTemplate).where(AIInfoTemplate.id == profile_template.info_id)
            )
            info_template = info_result.scalar_one_or_none()

        logger.debug(
            "profile_template_with_info_retrieved",
            profile_template_id=profile_template_id,
            has_info_template=info_template is not None,
        )

        return {
            "profile_template": profile_template,
            "info_template": info_template,
        }

    except Exception as e:
        logger.error(
            "profile_template_with_info_query_failed", error=str(e), profile_template_id=profile_template_id
        )
        return None


async def get_profile_template_by_id(db: AsyncSession, template_id: int) -> Optional[AIProfileTemplate]:
    """
    Get profile template by ID.

    Args:
        db: Database session
        template_id: Template ID

    Returns:
        Profile template object or None if not found
    """
    try:
        result = await db.execute(select(AIProfileTemplate).where(AIProfileTemplate.id == template_id))

        template = result.scalar_one_or_none()

        if not template:
            logger.warning("profile_template_not_found", template_id=template_id)

        return template

    except Exception as e:
        logger.error("profile_template_by_id_query_failed", error=str(e), template_id=template_id)
        return None


async def get_info_template_by_id(db: AsyncSession, template_id: int) -> Optional[AIInfoTemplate]:
    """
    Get info template by ID.

    Args:
        db: Database session
        template_id: Template ID

    Returns:
        Info template object or None if not found
    """
    try:
        result = await db.execute(select(AIInfoTemplate).where(AIInfoTemplate.id == template_id))

        template = result.scalar_one_or_none()

        if not template:
            logger.warning("info_template_not_found", template_id=template_id)

        return template

    except Exception as e:
        logger.error("info_template_by_id_query_failed", error=str(e), template_id=template_id)
        return None


async def check_template_reusability(
    db: AsyncSession, profile_template_id: int, info_template_id: Optional[int] = None
) -> Dict[str, bool]:
    """
    Check if templates can be reused (not marked as single-use).

    Args:
        db: Database session
        profile_template_id: Profile template ID
        info_template_id: Info template ID (optional)

    Returns:
        Dictionary with reusability status for each template
    """
    try:
        result = {
            "profile_template_reusable": True,
            "info_template_reusable": True,
        }

        # Check profile template
        profile_template = await get_profile_template_by_id(db, profile_template_id)
        if profile_template:
            # Assume templates are reusable unless marked otherwise
            # This logic can be extended based on actual template properties
            result["profile_template_reusable"] = getattr(profile_template, "is_reusable", True)
        else:
            result["profile_template_reusable"] = False

        # Check info template if provided
        if info_template_id:
            info_template = await get_info_template_by_id(db, info_template_id)
            if info_template:
                result["info_template_reusable"] = getattr(info_template, "is_reusable", True)
            else:
                result["info_template_reusable"] = False

        logger.debug(
            "template_reusability_checked",
            profile_template_id=profile_template_id,
            info_template_id=info_template_id,
            result=result,
        )

        return result

    except Exception as e:
        logger.error(
            "template_reusability_check_failed",
            error=str(e),
            profile_template_id=profile_template_id,
            info_template_id=info_template_id,
        )
        return {
            "profile_template_reusable": False,
            "info_template_reusable": False,
        }
