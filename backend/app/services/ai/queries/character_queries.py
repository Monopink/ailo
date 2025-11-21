"""
AI character-related query functions.

This module provides character-related read/query functions with clear
separation of concerns and pure function design.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.ai import (
    AICharacter,
    AIPersonality,
    AIPersonalityPlaceholder,
    AIStyle,
    AIRelationship,
    AIDimensionRelationshipMapping,
    AIStyleDimension,
    AIDimension,
)
from models.profile import Profile
from models.contact import Contact
from enums import ContactType
from utils.logging import get_logger
from exceptions import AIDataAccessError
from services.ai.types import (
    CharacterContext,
    CurrentRelationship,
    DimensionSpec,
    ProfileInfo,
    RelationshipCounts,
    StyleInfo,
    PersonalityInfo,
)

logger = get_logger(__name__)


async def get_character_context(
    db: AsyncSession,
    *,
    character_qiao_id: Optional[str] = None,
    character_id: Optional[int] = None,
) -> Optional[CharacterContext]:
    """Query complete character context exactly once per request."""

    if not character_qiao_id and not character_id:
        raise ValueError("character_qiao_id or character_id must be provided")

    try:
        stmt = (
            select(AICharacter, AIPersonality, AIStyle, Profile, AIRelationship)
            .join(AIPersonality, AICharacter.personality_id == AIPersonality.id)
            .join(AIStyle, AICharacter.style_id == AIStyle.id)
            .join(
                Profile,
                and_(Profile.owner_qiao_id == AICharacter.qiao_id, Profile.owner_type == 2),
            )
            .outerjoin(AIRelationship, AICharacter.relationship_id == AIRelationship.id)
        )
        if character_qiao_id:
            stmt = stmt.where(AICharacter.qiao_id == character_qiao_id)
        if character_id:
            stmt = stmt.where(AICharacter.id == character_id)

        result = await db.execute(stmt)
        row = result.first()
        if not row:
            logger.warning(
                "character_context_not_found",
                character_qiao_id=character_qiao_id,
                character_id=character_id,
            )
            return None

        character, personality, style, profile, relationship = row

        dimensions = await _get_style_dimensions(db, style.id)

        context: CharacterContext = {
            "character_id": character.id,
            "character_qiao_id": character.qiao_id,
            "category": character.category,
            "status": character.status,
            "created_by": character.created_by,
            "memory": character.memory,
            "prompt_variables": dict(character.prompt_variables or {}),
            "request_params": dict(character.request_params or {}),
            "typing_speed_wpm": character.typing_speed_wpm,
            "timezone": character.timezone or "Asia/Shanghai",
            "created_from_profile_qiao_id": character.created_from_profile_qiao_id,
            "relationship_id": character.relationship_id,
            "relationship_counts": _normalize_relationship_counts(character.relationship_counts),
            "style": _build_style(style),
            "personality": _build_personality(personality),
            "profile": _build_profile(profile),
            "current_relationship": _build_current_relationship(relationship),
            "dimensions": dimensions,
        }

        logger.debug(
            "character_context_loaded",
            character_qiao_id=context["character_qiao_id"],
            style_id=context["style"]["id"],
            dimension_count=len(dimensions),
        )

        return context

    except AIDataAccessError:
        raise
    except Exception as exc:
        logger.error(
            "character_context_query_failed",
            error=str(exc),
            character_qiao_id=character_qiao_id,
            character_id=character_id,
            exc_info=True,
        )
        raise AIDataAccessError(
            query="get_character_context",
            reason="query_failed",
            message="Failed to load character context",
            details={
                "character_qiao_id": character_qiao_id,
                "character_id": character_id,
            },
        ) from exc


async def get_personality_with_placeholders(
    db: AsyncSession, personality_id: int
) -> Optional[Dict[str, Any]]:
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

        # Get placeholders
        placeholders_result = await db.execute(
            select(AIPersonalityPlaceholder).where(
                AIPersonalityPlaceholder.personality_id == personality_id
            )
        )
        placeholders = list(placeholders_result.scalars().all())

        logger.debug(
            "personality_with_placeholders_retrieved",
            personality_id=personality_id,
            placeholders_count=len(placeholders),
        )

        return {
            "personality": personality,
            "placeholders": placeholders,
        }

    except Exception as e:
        logger.error(
            "personality_with_placeholders_query_failed", error=str(e), personality_id=personality_id
        )
        return None


async def _get_style_dimensions(db: AsyncSession, style_id: int) -> List[DimensionSpec]:
    result = await db.execute(
        select(
            AIDimension.id.label("id"),
            AIDimension.name.label("name"),
            AIDimension.display_name.label("display_name"),
            AIStyleDimension.initial_position.label("initial_position"),
        )
        .join(AIStyleDimension, AIStyleDimension.dimension_id == AIDimension.id)
        .where(AIStyleDimension.style_id == style_id)
        .order_by(AIDimension.name)
    )

    return [
        DimensionSpec(
            id=row.id,
            name=row.name,
            display_name=row.display_name,
            initial_position=row.initial_position,
        )
        for row in result
    ]


def _normalize_relationship_counts(raw_counts: Optional[Dict[str, Any]]) -> RelationshipCounts:
    if not raw_counts:
        return {}

    normalized: RelationshipCounts = {}
    for key, value in raw_counts.items():
        try:
            normalized[str(key)] = int(value)
        except (TypeError, ValueError):
            continue

    return normalized


def _build_style(style: AIStyle) -> StyleInfo:
    return StyleInfo(id=style.id, name=style.name, display_name=style.display_name)


def _build_personality(personality: AIPersonality) -> PersonalityInfo:
    return PersonalityInfo(
        id=personality.id,
        name=personality.name,
        display_name=personality.display_name,
        prompt=personality.prompt,
        status=personality.status,
        json_schema=getattr(personality, "json_schema", None),
    )


def _build_profile(profile: Profile) -> ProfileInfo:
    return ProfileInfo(
        nickname=profile.nickname,
        bio=profile.bio,
        gender=profile.gender,
        avatar_url=profile.avatar_url,
        avatar_prompt=getattr(profile, "avatar_prompt", None),
        region=getattr(profile, "region", None),
    )


def _build_current_relationship(relationship: Optional[AIRelationship]) -> Optional[CurrentRelationship]:
    if not relationship:
        return None

    return CurrentRelationship(
        id=relationship.id,
        name=relationship.name,
        display_name=relationship.display_name,
        prompt_fragment=relationship.prompt_fragment,
    )


async def get_style_with_relationships(db: AsyncSession, style_id: int) -> Optional[Dict[str, Any]]:
    """
    Get style with relationship mappings.

    Args:
        db: Database session
        style_id: Style ID

    Returns:
        Dictionary containing style and relationships, or None if not found
    """
    try:
        # Get style
        style_result = await db.execute(select(AIStyle).where(AIStyle.id == style_id))
        style = style_result.scalar_one_or_none()

        if not style:
            logger.warning("style_not_found", style_id=style_id)
            return None

        # Get dimension relationship mappings with dimension names
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
            .order_by(AIDimensionRelationshipMapping.start_position)
        )

        relationships = []
        for mapping, relationship, dimension in mappings_result:
            relationships.append(
                {
                    "mapping": mapping,
                    "relationship": relationship,
                    "dimension_id": mapping.dimension_id,
                    "dimension_name": dimension.name,
                    "start_position": mapping.start_position,
                    "end_position": mapping.end_position,
                    "priority": mapping.priority,
                }
            )

        logger.debug(
            "style_with_relationships_retrieved", style_id=style_id, relationships_count=len(relationships)
        )

        return {
            "style": style,
            "relationships": relationships,
        }

    except Exception as e:
        logger.error("style_with_relationships_query_failed", error=str(e), style_id=style_id)
        return None


async def get_character_relationship_config(
    db: AsyncSession,
    character_qiao_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch wake timing configuration for the character's current relationship.

    Returns None for first conversations (no relationship_id yet),
    the actual configuration when available, or a hard-coded default
    if the relationship row is missing/invalid.
    """

    try:
        stmt = (
            select(AICharacter.relationship_id, AIRelationship)
            .join(
                AIRelationship,
                AICharacter.relationship_id == AIRelationship.id,
                isouter=True,
            )
            .where(AICharacter.qiao_id == character_qiao_id)
        )
        result = await db.execute(stmt)
        row = result.first()

        if not row:
            logger.warning(
                "character_not_found_for_relationship_config",
                character_qiao_id=character_qiao_id,
            )
            return None

        relationship_id, relationship = row

        if relationship_id is None:
            return None  # First conversation: skip wake logic

        if not relationship:
            logger.warning(
                "relationship_config_missing",
                character_qiao_id=character_qiao_id,
                relationship_id=relationship_id,
            )
            return _default_relationship_timing()

        return {
            "wake_time_min_ms": int(relationship.wake_time_min_ms),
            "wake_time_max_ms": int(relationship.wake_time_max_ms),
            "wake_time_bias": relationship.wake_time_bias,
            "wake_window_ms": int(relationship.wake_window_ms),
            "wake_time_adjustment": relationship.wake_time_adjustment,
            "no_reply_probability": float(relationship.no_reply_probability or 0.0),
            "followup_delay_ms": int(getattr(relationship, "followup_delay_ms", 5000)),
        }

    except Exception as exc:
        logger.error(
            "relationship_config_fetch_failed",
            error=str(exc),
            character_qiao_id=character_qiao_id,
        )
        return _default_relationship_timing()


async def get_character_id_by_qiao_id(db: AsyncSession, character_qiao_id: str) -> Optional[int]:
    """
    Get character ID by qiao_id.

    Args:
        db: Database session
        character_qiao_id: Character's qiao_id

    Returns:
        Character ID or None if not found
    """
    try:
        result = await db.execute(select(AICharacter.id).where(AICharacter.qiao_id == character_qiao_id))

        character_id = result.scalar_one_or_none()

        if character_id is None:
            logger.warning("character_id_not_found", character_qiao_id=character_qiao_id)

        return character_id

    except Exception as e:
        logger.error("character_id_query_failed", error=str(e), character_qiao_id=character_qiao_id)
        return None


async def get_user_id_by_qiao_id(db: AsyncSession, user_qiao_id: str) -> Optional[int]:
    """
    Get user ID by qiao_id.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id

    Returns:
        User ID or None if not found
    """
    try:
        result = await db.execute(select(User.id).where(User.qiao_id == user_qiao_id))

        user_id = result.scalar_one_or_none()

        if user_id is None:
            logger.warning("user_id_not_found", user_qiao_id=user_qiao_id)

        return user_id

    except Exception as e:
        logger.error("user_id_query_failed", error=str(e), user_qiao_id=user_qiao_id)
        return None


async def get_all_characters(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Get all active characters for admin interface.

    Args:
        db: Database session

    Returns:
        List of character dictionaries with basic information
    """
    try:
        result = await db.execute(
            select(AICharacter, Profile, Contact.user_qiao_id)
            .outerjoin(Profile, AICharacter.qiao_id == Profile.owner_qiao_id)
            .outerjoin(
                Contact,
                and_(
                    Contact.contact_id == AICharacter.id,
                    Contact.contact_type == ContactType.AI,
                    Contact.is_deleted == 0,
                ),
            )
            .where(AICharacter.status == 1)  # active characters only
            .order_by(AICharacter.created_at.desc())
        )

        characters = []
        for character, profile, owner_qiao_id in result.all():
            characters.append(
                {
                    "id": character.id,
                    "qiao_id": character.qiao_id,
                    "name": (profile.nickname if profile else None) or f"Character {character.qiao_id}",
                    "category": character.category,
                    "user_qiao_id": owner_qiao_id,
                    "created_at": character.created_at.isoformat() if character.created_at else None,
                }
            )

        logger.debug(
            "all_characters_retrieved",
            count=len(characters),
        )

        return characters

    except Exception as e:
        logger.error(
            "all_characters_retrieval_failed",
            error=str(e),
        )
        return []


def _default_relationship_timing() -> Dict[str, Any]:
    """Provide sane defaults when relationship timing data is unavailable."""

    return {
        "wake_time_min_ms": 2000,
        "wake_time_max_ms": 4000,
        "wake_time_bias": "balanced",
        "wake_window_ms": 60000,
        "wake_time_adjustment": "random_half",
        "no_reply_probability": 0.0,
        "followup_delay_ms": 5000,
    }
