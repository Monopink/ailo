"""
AI template-related query functions.

This module provides template-related read/query functions with clear
separation of concerns and pure function design.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.ai.template import AIProfileTemplate, AICharacterTemplate
from utils.logging import get_logger

logger = get_logger(__name__)


async def get_profile_template_with_character_template(
    db: AsyncSession, profile_template_id: int
) -> Optional[Dict[str, Any]]:
    """
    Get profile template with associated character template.

    Args:
        db: Database session
        profile_template_id: Profile template ID

    Returns:
        Dictionary containing profile template and character template, or None if not found
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

        # Get associated character template
        character_template = None
        if profile_template.character_template_id:
            ct_result = await db.execute(
                select(AICharacterTemplate).where(
                    AICharacterTemplate.id == profile_template.character_template_id
                )
            )
            character_template = ct_result.scalar_one_or_none()

        logger.debug(
            "profile_template_with_character_template_retrieved",
            profile_template_id=profile_template_id,
            has_character_template=character_template is not None,
        )

        return {
            "profile_template": profile_template,
            "character_template": character_template,
        }

    except Exception as e:
        logger.error(
            "profile_template_with_character_template_query_failed",
            error=str(e),
            profile_template_id=profile_template_id,
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


async def get_character_template_by_id(
    db: AsyncSession, template_id: int
) -> Optional[AICharacterTemplate]:
    """
    Get character template by ID.

    Args:
        db: Database session
        template_id: Template ID

    Returns:
        Character template object or None if not found
    """
    try:
        result = await db.execute(
            select(AICharacterTemplate).where(AICharacterTemplate.id == template_id)
        )

        template = result.scalar_one_or_none()

        if not template:
            logger.warning("character_template_not_found", template_id=template_id)

        return template

    except Exception as e:
        logger.error("character_template_by_id_query_failed", error=str(e), template_id=template_id)
        return None


async def check_template_reusability(
    db: AsyncSession, profile_template_id: int, character_template_id: Optional[int] = None
) -> Dict[str, bool]:
    """
    Check if templates can be reused (not marked as single-use).

    Args:
        db: Database session
        profile_template_id: Profile template ID
        character_template_id: Character template ID (optional)

    Returns:
        Dictionary with reusability status for each template
    """
    try:
        result = {
            "profile_template_reusable": True,
            "character_template_reusable": True,
        }

        # Check profile template
        profile_template = await get_profile_template_by_id(db, profile_template_id)
        if profile_template:
            # Assume templates are reusable unless marked otherwise
            # This logic can be extended based on actual template properties
            result["profile_template_reusable"] = getattr(profile_template, "is_reusable", True)
        else:
            result["profile_template_reusable"] = False

        # Check character template if provided
        if character_template_id:
            character_template = await get_character_template_by_id(db, character_template_id)
            if character_template:
                result["character_template_reusable"] = getattr(
                    character_template, "is_reusable", True
                )
            else:
                result["character_template_reusable"] = False

        logger.debug(
            "template_reusability_checked",
            profile_template_id=profile_template_id,
            character_template_id=character_template_id,
            result=result,
        )

        return result

    except Exception as e:
        logger.error(
            "template_reusability_check_failed",
            error=str(e),
            profile_template_id=profile_template_id,
            character_template_id=character_template_id,
        )
        return {
            "profile_template_reusable": False,
            "character_template_reusable": False,
        }
