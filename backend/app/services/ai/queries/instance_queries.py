"""
AI instance-related query functions.

This module provides instance-related read/query functions with clear
separation of concerns and pure function design.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from models.ai import (
    AIInstance,
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
from models.user import User
from enums import ContactType
from utils.logging import get_logger
from exceptions import AIDataAccessError
from services.ai.types import (
    InstanceContext,
    CurrentRelationship,
    DimensionSpec,
    ProfileInfo,
    RelationshipCounts,
    StyleInfo,
    PersonalityInfo,
    AITypeInfo,
)

logger = get_logger(__name__)


async def get_instance_context(
    db: AsyncSession,
    *,
    instance_qiao_id: Optional[str] = None,
    instance_id: Optional[int] = None,
) -> Optional[InstanceContext]:
    """Query complete instance context exactly once per request."""

    if not instance_qiao_id and not instance_id:
        raise ValueError("instance_qiao_id or instance_id must be provided")

    try:
        stmt = (
            select(AIInstance, AIPersonality, AIStyle, Profile, AIRelationship)
            .join(AIPersonality, AIInstance.personality_id == AIPersonality.id)
            .join(AIStyle, AIInstance.style_id == AIStyle.id)
            .join(
                Profile,
                and_(Profile.owner_qiao_id == AIInstance.qiao_id, Profile.owner_type.in_([2, 3])),
            )
            .outerjoin(AIRelationship, AIInstance.relationship_id == AIRelationship.id)
        )
        if instance_qiao_id:
            stmt = stmt.where(AIInstance.qiao_id == instance_qiao_id)
        if instance_id:
            stmt = stmt.where(AIInstance.id == instance_id)

        result = await db.execute(stmt)
        row = result.first()
        if not row:
            logger.warning(
                "instance_context_not_found",
                instance_qiao_id=instance_qiao_id,
                instance_id=instance_id,
            )
            return None

        instance, personality, style, profile, relationship = row
        ai_type_info = _build_ai_type(instance.creation_metadata)

        dimensions = await _get_style_dimensions(db, style.id)

        context: InstanceContext = {
            "instance_id": instance.id,
            "instance_qiao_id": instance.qiao_id,
            "user_id": instance.user_id,
            "user_qiao_id": instance.user_qiao_id,
            "ai_type": ai_type_info,
            "status": instance.status,
            "created_by": instance.created_by,
            "memory": instance.memory,
            "prompt_variables": dict(instance.prompt_variables or {}),
            "request_params": dict(instance.request_params or {}),
            "typing_speed_wpm": instance.typing_speed_wpm,
            "timezone": instance.timezone or "Asia/Shanghai",
            "created_from_profile_qiao_id": getattr(instance, "created_from_profile_qiao_id", None),
            "relationship_id": instance.relationship_id,
            "relationship_counts": _normalize_relationship_counts(instance.relationship_counts),
            "style": _build_style(style),
            "personality": _build_personality(personality),
            "profile": _build_profile(profile),
            "current_relationship": _build_current_relationship(relationship),
            "dimensions": dimensions,
        }

        logger.debug(
            "instance_context_loaded",
            instance_qiao_id=context["instance_qiao_id"],
            style_id=context["style"]["id"],
            dimension_count=len(dimensions),
        )

        return context

    except AIDataAccessError:
        raise
    except Exception as exc:
        logger.error(
            "instance_context_query_failed",
            error=str(exc),
            instance_qiao_id=instance_qiao_id,
            instance_id=instance_id,
            exc_info=True,
        )
        raise AIDataAccessError(
            query="get_instance_context",
            reason="query_failed",
            message="Failed to load instance context",
            details={
                "instance_qiao_id": instance_qiao_id,
                "instance_id": instance_id,
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
    return StyleInfo(id=style.id, display_name=style.display_name)


def _build_personality(personality: AIPersonality) -> PersonalityInfo:
    return PersonalityInfo(
        id=personality.id,
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


def _build_ai_type(creation_metadata: Optional[Dict[str, Any]]) -> Optional[AITypeInfo]:
    if not creation_metadata:
        return None

    def _parse_type_id(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    type_id = creation_metadata.get("persona_type_id") or creation_metadata.get("template_type_id")
    type_name = (
        creation_metadata.get("persona_type_name")
        or creation_metadata.get("template_type_name")
    )
    parsed_type_id = _parse_type_id(type_id)

    if parsed_type_id is None or not type_name:
        return None

    return {"id": parsed_type_id, "display_name": str(type_name)}


def _build_current_relationship(relationship: Optional[AIRelationship]) -> Optional[CurrentRelationship]:
    if not relationship:
        return None

    return CurrentRelationship(
        id=relationship.id,
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


async def get_instance_relationship_config(
    db: AsyncSession,
    instance_qiao_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch wake timing configuration for the instance's current relationship.

    Returns None for first conversations (no relationship_id yet),
    the actual configuration when available, or a hard-coded default
    if the relationship row is missing/invalid.
    """

    try:
        stmt = (
            select(AIInstance.relationship_id, AIRelationship)
            .join(
                AIRelationship,
                AIInstance.relationship_id == AIRelationship.id,
                isouter=True,
            )
            .where(AIInstance.qiao_id == instance_qiao_id)
        )
        result = await db.execute(stmt)
        row = result.first()

        if not row:
            logger.warning(
                "instance_not_found_for_relationship_config",
                instance_qiao_id=instance_qiao_id,
            )
            return None

        relationship_id, relationship = row

        if relationship_id is None:
            return None  # First conversation: skip wake logic

        if not relationship:
            logger.warning(
                "relationship_config_missing",
                instance_qiao_id=instance_qiao_id,
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
            instance_qiao_id=instance_qiao_id,
        )
        return _default_relationship_timing()


async def get_instance_id_by_qiao_id(db: AsyncSession, instance_qiao_id: str) -> Optional[int]:
    """
    Get instance ID by qiao_id.

    Args:
        db: Database session
        instance_qiao_id: Instance's qiao_id

    Returns:
        Instance ID or None if not found
    """
    try:
        result = await db.execute(select(AIInstance.id).where(AIInstance.qiao_id == instance_qiao_id))

        instance_id = result.scalar_one_or_none()

        if instance_id is None:
            logger.warning("instance_id_not_found", instance_qiao_id=instance_qiao_id)

        return instance_id

    except Exception as e:
        logger.error("instance_id_query_failed", error=str(e), instance_qiao_id=instance_qiao_id)
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


async def get_all_instances(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Get all active instances for admin interface.

    Args:
        db: Database session

    Returns:
        List of instance dictionaries with basic information
    """
    try:
        result = await db.execute(
            select(AIInstance, Profile, Contact.user_qiao_id)
            .outerjoin(Profile, AIInstance.qiao_id == Profile.owner_qiao_id)
            .outerjoin(
                Contact,
                and_(
                    Contact.contact_id == AIInstance.id,
                    Contact.contact_type == ContactType.AI,
                    Contact.is_deleted == 0,
                ),
            )
            .where(AIInstance.status == 1)  # active instances only
            .order_by(AIInstance.created_at.desc())
        )

        instances = []
        for instance, profile, owner_qiao_id in result.all():
            instances.append(
                {
                    "id": instance.id,
                    "qiao_id": instance.qiao_id,
                    "name": (profile.nickname if profile else None) or f"Instance {instance.qiao_id}",
                    "ai_type": _build_ai_type(instance.creation_metadata),
                    "user_qiao_id": owner_qiao_id,
                    "created_at": instance.created_at.isoformat() if instance.created_at else None,
                }
            )

        logger.debug(
            "all_instances_retrieved",
            count=len(instances),
        )

        return instances

    except Exception as e:
        logger.error(
            "all_instances_retrieval_failed",
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
