"""
AI instance-related query functions.

This module provides instance-related read/query functions with clear
separation of concerns and pure function design.
"""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ContactType
from app.exceptions import AIDataAccessError
from app.models.ai import (
    AIDimension,
    AIDimensionRelationshipMapping,
    AIInstance,
    AIPersonality,
    AIPersonalityPlaceholder,
    AIRelationship,
    AIStyle,
    AIStyleDimension,
)
from app.models.contact import Contact
from app.models.profile import Profile
from app.models.user import User
from app.services.profile.avatar import get_avatar_url
from app.type_defs import (
    AITypeInfo,
    CurrentRelationship,
    DimensionSpec,
    InstanceContext,
    JSONDict,
    PersonalityInfo,
    ProfileInfo,
    RelationshipCounts,
    RelationshipMapping,
    RelationshipTiming,
    StyleInfo,
)
from app.utils.logging import get_logger
from app.utils.validation import validate_typed_dict

logger = get_logger(__name__)


async def get_instance_context(
    db: AsyncSession,
    *,
    instance_qiao_id: str | None = None,
    user_qiao_id: str | None = None,
    instance_id: int | None = None,
) -> InstanceContext | None:
    """Query complete instance context exactly once per request.

    Requires instance_id, or (instance_qiao_id and user_qiao_id) for disambiguation.
    """

    if instance_id is None:
        if not instance_qiao_id or not user_qiao_id:
            raise ValueError("instance_id or (instance_qiao_id and user_qiao_id) must be provided")

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
        if instance_id is not None:
            stmt = stmt.where(AIInstance.id == instance_id)
        else:
            stmt = stmt.where(
                AIInstance.qiao_id == instance_qiao_id,
                AIInstance.user_qiao_id == user_qiao_id,
            )

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

        dimensions = await get_style_dimensions(db, style.id)

        avatar_url = await get_avatar_url(profile)

        context: InstanceContext = {
            "instance_id": instance.id,
            "instance_qiao_id": instance.qiao_id,
            "user_id": instance.user_id,
            "user_qiao_id": instance.user_qiao_id,
            "ai_type": ai_type_info,
            "status": instance.status,
            "created_by": instance.created_by,
            "llm_config_id": instance.llm_config_id,
            "prompt_variables": dict(instance.prompt_variables or {}),
            "request_params": dict(instance.request_params or {}),
            "typing_speed_wpm": instance.typing_speed_wpm,
            "timezone": instance.timezone or "Asia/Shanghai",
            "created_from_profile_qiao_id": getattr(instance, "created_from_profile_qiao_id", None),
            "relationship_id": instance.relationship_id,
            "relationship_counts": _normalize_relationship_counts(instance.relationship_counts),
            "style": _build_style(style),
            "personality": _build_personality(personality),
            "profile": _build_profile(profile, avatar_url),
            "current_relationship": _build_current_relationship(relationship),
            "dimensions": dimensions,
        }

        validate_typed_dict(context, InstanceContext)

        logger.debug(
            "instance_context_loaded",
            instance_qiao_id=context["instance_qiao_id"],
            style_id=context["style"]["id"],
            dimension_count=len(dimensions),
        )

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
    else:
        return context


async def get_personality_with_placeholders(
    db: AsyncSession, personality_id: int
) -> dict[str, object] | None:
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

        payload = {
            "personality": personality,
            "placeholders": placeholders,
        }

    except Exception as exc:
        logger.error(
            "personality_with_placeholders_query_failed",
            error=str(exc),
            personality_id=personality_id,
        )
        return None
    else:
        return payload


async def get_style_dimensions(db: AsyncSession, style_id: int) -> list[DimensionSpec]:
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


def _normalize_relationship_counts(raw_counts: JSONDict | None) -> RelationshipCounts:
    if not raw_counts:
        return {}

    normalized: RelationshipCounts = {}
    for key, value in raw_counts.items():
        coerced_value = _coerce_relationship_count(value)
        if coerced_value is None:
            continue
        normalized[str(key)] = coerced_value

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


def _build_profile(profile: Profile, avatar_url: str | None) -> ProfileInfo:
    return ProfileInfo(
        nickname=_resolve_profile_nickname(profile),
        bio=profile.bio,
        gender=profile.gender,
        avatar_url=avatar_url,
        avatar_prompt=getattr(profile, "avatar_prompt", None),
        region=getattr(profile, "region", None),
    )


def _build_ai_type(creation_metadata: JSONDict | None) -> AITypeInfo | None:
    if not creation_metadata:
        return None

    def _parse_type_id(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int | float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    type_id = creation_metadata.get("persona_type_id") or creation_metadata.get("template_type_id")
    type_name = creation_metadata.get("persona_type_name") or creation_metadata.get(
        "template_type_name"
    )
    parsed_type_id = _parse_type_id(type_id)

    if parsed_type_id is None or not type_name:
        return None

    return {"id": parsed_type_id, "display_name": str(type_name)}


def _build_current_relationship(relationship: AIRelationship | None) -> CurrentRelationship | None:
    if not relationship:
        return None

    return CurrentRelationship(
        id=relationship.id,
        display_name=relationship.display_name,
        prompt_fragment=relationship.prompt_fragment or "",
    )


async def get_style_with_relationships(db: AsyncSession, style_id: int) -> dict[str, object] | None:
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

        relationships: list[RelationshipMapping] = []
        for mapping, relationship, dimension in mappings_result:
            relationships.append(
                RelationshipMapping(
                    relationship=relationship,
                    dimension_name=dimension.name,
                    start_position=mapping.start_position,
                    end_position=mapping.end_position,
                    priority=mapping.priority,
                    limit_count=mapping.limit_count,
                )
            )

        logger.debug(
            "style_with_relationships_retrieved",
            style_id=style_id,
            relationships_count=len(relationships),
        )

        payload = {
            "style": style,
            "relationships": relationships,
        }

    except Exception as exc:
        logger.error("style_with_relationships_query_failed", error=str(exc), style_id=style_id)
        return None
    else:
        return payload


async def get_instance_relationship_config(
    db: AsyncSession,
    *,
    instance_id: int | None = None,
    user_qiao_id: str | None = None,
    instance_qiao_id: str | None = None,
) -> RelationshipTiming | None:
    """
    Fetch wake timing configuration for the instance's current relationship.

    Requires instance_id, or (instance_qiao_id and user_qiao_id) for disambiguation.

    Returns None for first conversations (no relationship_id yet),
    the actual configuration when available, or a hard-coded default
    if the relationship row is missing/invalid.
    """

    if instance_id is None:
        if not instance_qiao_id or not user_qiao_id:
            raise ValueError("instance_id or (instance_qiao_id and user_qiao_id) must be provided")

    try:
        stmt = select(AIInstance.relationship_id, AIRelationship).join(
            AIRelationship,
            AIInstance.relationship_id == AIRelationship.id,
            isouter=True,
        )
        if instance_id is not None:
            stmt = stmt.where(AIInstance.id == instance_id)
        else:
            stmt = stmt.where(
                AIInstance.qiao_id == instance_qiao_id,
                AIInstance.user_qiao_id == user_qiao_id,
            )
        result = await db.execute(stmt)
        row = result.first()

        if not row:
            logger.warning(
                "instance_not_found_for_relationship_config",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
                instance_id=instance_id,
            )
            return None

        relationship_id, relationship = row

        if relationship_id is None:
            return None  # First conversation: skip wake logic

        timing: RelationshipTiming
        if not relationship:
            logger.warning(
                "relationship_config_missing",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
                instance_id=instance_id,
                relationship_id=relationship_id,
            )
            timing = _default_relationship_timing()
        else:
            timing = {
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
            user_qiao_id=user_qiao_id,
            instance_id=instance_id,
        )
        return _default_relationship_timing()
    else:
        validate_typed_dict(timing, RelationshipTiming, name="RelationshipTiming")
        return timing


async def get_instance_id_by_qiao_id(
    db: AsyncSession, instance_qiao_id: str, user_qiao_id: str
) -> int | None:
    """
    Get instance ID by qiao_id for a specific user.

    Args:
        db: Database session
        instance_qiao_id: Instance's qiao_id
        user_qiao_id: User's qiao_id

    Returns:
        Instance ID or None if not found
    """
    try:
        result = await db.execute(
            select(AIInstance.id).where(
                AIInstance.qiao_id == instance_qiao_id,
                AIInstance.user_qiao_id == user_qiao_id,
            )
        )

        instance_id = result.scalar_one_or_none()

        if instance_id is None:
            logger.warning(
                "instance_id_not_found",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
            )

    except Exception as exc:
        logger.error(
            "instance_id_query_failed",
            error=str(exc),
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
        )
        return None
    else:
        return instance_id


async def get_user_id_by_qiao_id(db: AsyncSession, user_qiao_id: str) -> int | None:
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

    except Exception as exc:
        logger.error("user_id_query_failed", error=str(exc), user_qiao_id=user_qiao_id)
        return None
    else:
        return user_id


async def get_all_instances(db: AsyncSession) -> list[JSONDict]:
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
                    "name": (profile.nickname if profile else None)
                    or f"Instance {instance.qiao_id}",
                    "ai_type": _build_ai_type(instance.creation_metadata),
                    "user_qiao_id": owner_qiao_id,
                    "created_at": instance.created_at.isoformat() if instance.created_at else None,
                }
            )

        logger.debug(
            "all_instances_retrieved",
            count=len(instances),
        )

    except Exception as exc:
        logger.error(
            "all_instances_retrieval_failed",
            error=str(exc),
        )
        return []
    else:
        return instances


def _default_relationship_timing() -> RelationshipTiming:
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


def _resolve_profile_nickname(profile: Profile) -> str:
    """
    Normalize profile nickname for TypedDict requirements.

    Falls back to owner qiao_id when nickname is not populated.
    """
    nickname = getattr(profile, "nickname", None)
    if isinstance(nickname, str) and nickname:
        return nickname
    fallback = getattr(profile, "owner_qiao_id", None)
    if isinstance(fallback, str) and fallback:
        return fallback
    return "Unknown"


def _coerce_relationship_count(value: object) -> int | None:
    """Convert JSON-style counters to integers."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
