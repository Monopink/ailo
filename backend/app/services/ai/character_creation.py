"""
AI character creation service.

This module handles creating AI character instances from templates.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from crud.ai import ai_character, ai_profile_template, ai_info_template
from models.ai import AICharacter
from schemas.ai import AICharacterCreate
from enums import AICharacterCreator
from utils.logging import get_logger

logger = get_logger(__name__)


async def create_character_from_template(
    db: AsyncSession, template_qiao_id: str, user_qiao_id: str, user_id: int
) -> AICharacter:
    """
    Create AI character instance from profile template.

    Args:
        db: Database session
        template_qiao_id: Profile template qiao_id
        user_qiao_id: Owner user qiao_id
        user_id: Owner user ID

    Returns:
        Created AI character

    Raises:
        ValueError: If template not found or invalid
    """
    # 1. Query profile template
    profile_template = await ai_profile_template.get_by_qiao_id(db, qiao_id=template_qiao_id)
    if not profile_template:
        logger.error("profile_template_not_found", template_qiao_id=template_qiao_id)
        raise ValueError("Profile template not found")

    if profile_template.status != 1:
        logger.error("profile_template_inactive", template_qiao_id=template_qiao_id)
        raise ValueError("Profile template is inactive")

    # 2. Query info template
    info_template = await ai_info_template.get(db, id=profile_template.info_id)
    if not info_template:
        logger.error("info_template_not_found", info_id=profile_template.info_id)
        raise ValueError("Info template not found")

    if info_template.status != 1:
        logger.error("info_template_inactive", info_id=profile_template.info_id)
        raise ValueError("Info template is inactive")

    # 3. Create AI character
    character_data = AICharacterCreate(
        user_id=user_id,
        user_qiao_id=user_qiao_id,
        category=profile_template.category,
        style_id=info_template.style_id,
        personality_id=info_template.personality_id,
        status=1,  # active
        memory=info_template.memory,
        prompt_variables=info_template.prompt_variables,
        score_offset_algorithm=info_template.score_offset_algorithm,
        score_offset_params=info_template.score_offset_params,
        request_params=None,
        created_by=AICharacterCreator.USER,
    )

    character = await ai_character.create(db, obj_in=character_data)

    logger.info(
        "character_created_from_template",
        character_qiao_id=character.qiao_id,
        template_qiao_id=template_qiao_id,
        user_qiao_id=user_qiao_id,
    )

    # 4. Initialize relationship scores
    await initialize_relationship_scores(db, character.id, info_template.style_id)

    return character


async def initialize_relationship_scores(db: AsyncSession, character_id: int, style_id: int) -> None:
    """
    Initialize relationship scores for a new character.

    Args:
        db: Database session
        character_id: Character ID
        style_id: Style ID

    Raises:
        ValueError: If style not found or has no dimensions
    """
    from crud.ai.style import ai_style
    from models.ai import AIRelationshipScore

    # Query style with dimensions
    style = await ai_style.get(db, id=style_id)
    if not style:
        logger.error("style_not_found", style_id=style_id)
        raise ValueError("AI style not found")

    # Query dimensions for this style
    from sqlalchemy import select
    from models.ai.style import AIStyleDimension

    result = await db.execute(select(AIStyleDimension).where(AIStyleDimension.style_id == style_id))
    dimensions = result.scalars().all()

    if not dimensions:
        logger.error("style_has_no_dimensions", style_id=style_id)
        raise ValueError("AI style has no dimensions configured")

    # Create initial scores for each dimension
    from utils.snowflake import generate_snowflake_id

    for dimension in dimensions:
        score_data = {
            "id": generate_snowflake_id(),
            "character_id": character_id,
            "dimension_id": dimension.id,
            "score": dimension.default_score,  # Use default score from dimension
        }
        score_obj = AIRelationshipScore(**score_data)
        db.add(score_obj)

    await db.flush()

    logger.info(
        "relationship_scores_initialized",
        character_id=character_id,
        style_id=style_id,
        dimension_count=len(dimensions),
    )
