"""
AI prompt building and template processing module.

This module handles system prompt construction, placeholder replacement,
and JSON schema building for AI responses.
"""

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pendulum
from pendulum import DateTime as PendulumDateTime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.common import ConversationRole
from app.exceptions import AIServiceError
from app.models.ai import AIConversationState
from app.services.ai.memory import build_memory_prompt
from app.type_defs import InstanceContext, JSONValue, ProfileInfo
from app.utils.logging import get_logger

from .queries import get_conversation_contexts, get_personality_with_placeholders, get_user_profile
from .relationship_scoring import get_relationship_scores
from .utils.time_context import build_current_datetime

logger = get_logger(__name__)

# Constants for magic values
_TEMPLATE_PREVIEW_LENGTH = 200
_MIN_PROMPT_LENGTH = 10
_DAYS_IN_WEEK_START = 2
_DAYS_IN_WEEK_END = 6
_DAYS_IN_MONTH_START = 7
_DAYS_IN_MONTH_END = 30
_DAYS_IN_YEAR_START = 31
_DAYS_IN_YEAR = 365


# Exception classes moved to exceptions/business.py for consistency


def _raise_personality_not_found(personality_id: int | str) -> None:
    """Raise AIServiceError for personality not found."""
    raise AIServiceError(
        ai_service="prompt_building",
        reason="personality_not_found",
        message=f"Personality not found: {personality_id}",
    )


def _coerce_str_list(value: JSONValue | None) -> list[str]:
    """Convert JSON list payloads into a list of strings."""

    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def _coerce_non_negative_int(value: JSONValue | None, fallback: int) -> int:
    """Convert JSON number payloads into a non-negative integer."""

    parsed = fallback
    if isinstance(value, bool | int | float):
        parsed = int(value)
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError:
            return fallback
    else:
        return fallback

    return parsed if parsed >= 0 else fallback


async def build_system_prompt(
    db: AsyncSession,
    context: InstanceContext,
    relationship_type: dict[str, Any] | None,
    user_qiao_id: str,
) -> str:
    """
    Build complete system prompt for an AI instance.

    This implements step 7 from the prototype design:
    Apply relationship prompt and placeholders to personality template.

    Args:
        db: Database session
        context: Instance context dictionary
        relationship_type: Relationship type information
        user_qiao_id: User's qiao_id

    Returns:
        Complete system prompt string

    Raises:
        PromptBuildError: If prompt building fails
    """
    try:
        personality_id = context["personality"]["id"]

        personality_data = await get_personality_with_placeholders(db, personality_id)
        if personality_data is None:
            _raise_personality_not_found(personality_id)

        # Type narrowing: personality_data is guaranteed to be dict here
        assert personality_data is not None
        raw_placeholders = personality_data.get("placeholders")
        available_placeholders: list[Any] = (
            list(raw_placeholders) if isinstance(raw_placeholders, list) else []
        )

        # Build placeholder values
        placeholder_values = await _build_placeholder_values(
            db, context, relationship_type, user_qiao_id, available_placeholders
        )

        # Apply instance-specific prompt variables (overrides)
        instance_prompt_variables = context.get("prompt_variables") or {}
        placeholder_values.update(instance_prompt_variables)

        # Replace placeholders in personality prompt
        system_prompt = replace_placeholders(context["personality"]["prompt"], placeholder_values)

        logger.debug(
            "system_prompt_built",
            personality_id=personality_id,
            user_qiao_id=user_qiao_id,
            prompt_length=len(system_prompt),
            placeholders_used=len(placeholder_values),
        )

    except AIServiceError:
        raise
    except Exception as e:
        logger.error(
            "system_prompt_build_failed",
            error=str(e),
            instance_qiao_id=context.get("instance_qiao_id"),
            user_qiao_id=user_qiao_id,
            exc_info=True,
        )
        raise AIServiceError(
            ai_service="prompt_building",
            reason="build_failed",
            message=f"Failed to build system prompt: {e!s}",
        ) from e

    return system_prompt


def replace_placeholders(template: str, placeholders: dict[str, Any]) -> str:
    """
    Replace placeholders in template string.

    Placeholders use {{variable_name}} format.
    System placeholders take priority over instance-specific ones.
    Unknown placeholders are detected, logged, and cleared.

    Args:
        template: Template string with placeholders
        placeholders: Dictionary of placeholder values

    Returns:
        Template with placeholders replaced and unknown placeholders cleared
    """
    result = template
    replaced_count = 0
    failed_count = 0

    # Replace known placeholders
    for key, value in placeholders.items():
        placeholder_pattern = f"{{{{{key}}}}}"
        if placeholder_pattern in result:
            try:
                # Convert value to string, handling None values
                str_value = str(value) if value is not None else ""
                result = result.replace(placeholder_pattern, str_value)
                replaced_count += 1
            except Exception as e:
                # Clear the placeholder if replacement fails
                logger.warning(
                    "placeholder_replacement_failed_clearing",
                    key=key,
                    error=str(e),
                    placeholder_pattern=placeholder_pattern,
                )
                result = result.replace(placeholder_pattern, "")
                failed_count += 1

    # Detect and clear unknown placeholders
    unknown_pattern = r"\{\{([^}]+)\}\}"
    unknown_matches = re.findall(unknown_pattern, result)

    if unknown_matches:
        logger.warning(
            "unknown_placeholders_detected_clearing",
            unknown_placeholders=unknown_matches,
            template_preview=(
                template[:_TEMPLATE_PREVIEW_LENGTH]
                if len(template) > _TEMPLATE_PREVIEW_LENGTH
                else template
            ),
        )
        # Clear all unknown placeholders
        result = re.sub(unknown_pattern, "", result)

    logger.debug(
        "placeholders_processed",
        original_length=len(template),
        result_length=len(result),
        total_placeholders=len(placeholders),
        replaced_count=replaced_count,
        failed_count=failed_count,
        unknown_count=len(unknown_matches) if unknown_matches else 0,
    )

    return result


async def _build_placeholder_values(
    db: AsyncSession,
    context: InstanceContext,
    relationship_type: dict[str, Any] | None,
    user_qiao_id: str,
    available_placeholders: list[Any],
) -> dict[str, Any]:
    """
    Build placeholder values for system prompt.

    Args:
        db: Database session
        context: Instance context data
        relationship_type: Relationship type information
        user_qiao_id: User's qiao_id
        available_placeholders: Available placeholder definitions

    Returns:
        Dictionary of placeholder values
    """
    placeholder_values: dict[str, Any] = {}

    # System placeholders (highest priority)

    # {{relationship_prompt}} - relationship prompt fragment
    if relationship_type and relationship_type.get("relationship"):
        relationship = relationship_type["relationship"]
        placeholder_values["relationship_prompt"] = relationship.prompt_fragment or ""
    else:
        placeholder_values["relationship_prompt"] = ""

    # {{self_profile}} - instance profile description
    profile_payload = context.get("profile")
    instance_profile: ProfileInfo | None = (
        profile_payload if isinstance(profile_payload, dict) else None
    )
    if instance_profile:
        placeholder_values["self_profile"] = _format_profile(instance_profile)
    else:
        placeholder_values["self_profile"] = ""

    # {{other_profile}} - user profile description
    user_profile = await _get_user_profile(db, user_qiao_id)
    if user_profile:
        placeholder_values["other_profile"] = _format_profile(user_profile)
    else:
        placeholder_values["other_profile"] = ""

    # {{current_datetime}} - current date and time
    placeholder_values["current_datetime"] = _get_current_datetime(context)

    # {{memory}} - instance memory summary
    placeholder_values["memory"] = await build_memory_prompt(db, context)

    # {{score:dimension_name}} - dynamic score placeholders
    instance_qiao_id = context.get("instance_qiao_id")
    if instance_qiao_id:
        score_placeholders = await _build_score_placeholders(db, context["instance_id"])
        placeholder_values.update(score_placeholders)

        pending_text = await _build_pending_messages_placeholder(db, user_qiao_id, instance_qiao_id)
        placeholder_values["pending_messages"] = pending_text
    else:
        placeholder_values["pending_messages"] = ""

    # Fill in template-defined placeholders with defaults if not already provided
    if available_placeholders:
        for placeholder in available_placeholders:
            key: str | None = None
            if isinstance(placeholder, dict):
                key = placeholder.get("placeholder_key")
            else:
                key = getattr(placeholder, "placeholder_key", None)

            if not key or key in placeholder_values:
                continue

            placeholder_values[key] = ""

    logger.debug(
        "placeholder_values_built",
        user_qiao_id=user_qiao_id,
        placeholders_count=len(placeholder_values),
    )

    return placeholder_values


async def _build_score_placeholders(db: AsyncSession, instance_id: int) -> dict[str, str]:
    """
    Build score-related placeholders for an instance.

    Args:
        db: Database session
        instance_id: Instance ID

    Returns:
        Dictionary of score placeholders in format {"score:dimension_name": "value"}
    """
    scores = await get_relationship_scores(db, instance_id)
    if not scores:
        logger.debug(
            "no_scores_found_for_placeholders",
            instance_id=instance_id,
        )
        return {}

    score_placeholders = {}
    for score in scores:
        dimension_name = score["dimension_name"]
        score_value = score["score"]
        placeholder_key = f"score:{dimension_name}"
        score_placeholders[placeholder_key] = str(score_value)

    logger.debug(
        "score_placeholders_built",
        instance_id=instance_id,
        placeholders_count=len(score_placeholders),
    )

    return score_placeholders


async def _build_pending_messages_placeholder(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
) -> str:
    """
    Format pending messages (if any) so they can be injected into system prompt.
    """
    result = await db.execute(
        select(AIConversationState.pending_messages).where(
            AIConversationState.user_qiao_id == user_qiao_id,
            AIConversationState.instance_qiao_id == instance_qiao_id,
        )
    )
    pending_data = result.scalar_one_or_none()
    if not isinstance(pending_data, dict):
        return ""

    outgoing = _coerce_str_list(pending_data.get("outgoing"))
    if not outgoing:
        return ""

    total = _coerce_non_negative_int(pending_data.get("total_pending"), len(outgoing))
    message_lines = "\n".join(f"- {msg}" for msg in outgoing)
    return (
        f"【系统提示】你有 {total} 条消息因被打断而未发送:\n"
        f"{message_lines}\n"
        "请在本次回复中优先考虑这些未发送的内容。"
    )


def _format_profile(profile: dict[str, Any] | object) -> str:
    """
    Format profile information for prompt.

    Args:
        profile: Profile model instance

    Returns:
        Formatted profile string
    """
    try:
        parts = []

        # Support both dict and object
        nickname = (
            profile.get("nickname")
            if isinstance(profile, dict)
            else getattr(profile, "nickname", None)
        )
        gender = (
            profile.get("gender") if isinstance(profile, dict) else getattr(profile, "gender", None)
        )
        bio = profile.get("bio") if isinstance(profile, dict) else getattr(profile, "bio", None)
        region = (
            profile.get("region") if isinstance(profile, dict) else getattr(profile, "region", None)
        )

        if nickname:
            parts.append(f"昵称: {nickname}")

        if gender:
            gender_map = {1: "男", 2: "女", 3: "其他", 4: "未知"}
            gender_str = gender_map.get(gender, "未知")
            parts.append(f"性别: {gender_str}")

        if bio:
            parts.append(f"简介: {bio}")

        if region:
            parts.append(f"地区: {region}")

        return "; ".join(parts) if parts else "暂无资料"

    except Exception as exc:
        logger.error("profile_formatting_failed", error=str(exc), exc_info=True)
        return "资料格式化失败"


async def _get_user_profile(db: AsyncSession, user_qiao_id: str) -> dict[str, Any] | None:
    """
    Get user profile information.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id

    Returns:
        User profile or None
    """
    return await get_user_profile(db, user_qiao_id)


def _get_current_datetime(context: dict[str, Any] | InstanceContext) -> str:
    """
    Get current datetime string based on instance timezone.

    Falls back to Asia/Shanghai when timezone is invalid or missing.
    """
    try:
        return build_current_datetime(context)

    except Exception as exc:
        logger.error("datetime_formatting_failed", error=str(exc), exc_info=True)
        return "时间获取失败"


async def build_conversation_context(
    db: AsyncSession,
    instance_qiao_id: str,
    user_qiao_id: str,
    max_context_length: int | None = None,
    instance_timezone: str | None = None,
) -> list[dict[str, Any]]:
    """
    Build conversation context from AI contexts table.

    Args:
        db: Database session
        instance_qiao_id: Instance's qiao_id
        user_qiao_id: User's qiao_id
        max_context_length: Maximum number of context entries to include

    Returns:
        List of message dictionaries with 'role' and 'content' keys

    Raises:
        AIServiceError: If context building fails
    """
    try:
        # Get conversation contexts; when max_context_length is None, include all
        contexts = await get_conversation_contexts(
            db, instance_qiao_id, user_qiao_id, max_context_length
        )

        if not contexts:
            logger.debug(
                "no_conversation_contexts_found",
                instance_qiao_id=instance_qiao_id,
                user_qiao_id=user_qiao_id,
            )
            return []

        # Convert contexts to business-format message dictionaries
        messages: list[dict[str, Any]] = []
        for context in contexts:
            role = _map_context_role_to_message_role(
                context.get("role", ConversationRole.USER.value)
            )
            message_type = context.get("message_type", "text")
            text_content = context.get("text_content")
            media_url = context.get("media_url")
            media_metadata = context.get("media_metadata")
            created_at = context.get("created_at")

            if message_type == "text" and text_content:
                prefix = _format_time_prefix(created_at, instance_timezone)
                if prefix:
                    text_content = f"[{prefix}] {text_content}"

            messages.append(
                {
                    "role": role,
                    "message_type": message_type,
                    "text_content": text_content,
                    "media_url": media_url,
                    "media_metadata": media_metadata,
                }
            )

        logger.debug(
            "conversation_context_built",
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
            contexts_count=len(contexts),
            messages_count=len(messages),
        )

    except Exception as e:
        logger.error(
            "conversation_context_build_failed",
            error=str(e),
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
            exc_info=True,
        )
        raise AIServiceError(
            ai_service="context_building",
            reason="build_failed",
            message=f"Failed to build conversation context: {e!s}",
        ) from e

    return messages


def _map_context_role_to_message_role(role: str) -> str:
    """
    Map context role enum to message role string.

    Args:
        role: Role string value ("system"/"user"/"assistant")

    Returns:
        Message role string
    """
    role_mapping = {
        ConversationRole.SYSTEM.value: "system",
        ConversationRole.USER.value: "user",
        ConversationRole.ASSISTANT.value: "assistant",
    }
    return role_mapping.get(role, "user")


def _format_time_prefix(created_at: datetime | None, instance_timezone: str | None) -> str | None:
    """
    Format timestamp for conversation history using instance timezone with humanized relative time.

    Examples:
    - [2024-11-18(一年前) 17:19]
    - [10-18(一个月前) 17:19]
    - [11-18(五天前) 17:19]
    - [昨天17:19]
    - [今天17:19]

    Falls back to Asia/Shanghai timezone.
    Uses Pendulum for simplified timezone handling.
    """
    try:
        if created_at is None:
            return None

        tz_name = instance_timezone or "Asia/Shanghai"

        # Convert to Pendulum instance (handles naive datetime automatically)
        try:
            pdt: PendulumDateTime = pendulum.instance(created_at, tz="UTC")
            local_dt = pdt.in_timezone(tz_name)
        except Exception:
            # Fallback to Asia/Shanghai if timezone is invalid
            pdt = pendulum.instance(created_at, tz="UTC")
            local_dt = pdt.in_timezone("Asia/Shanghai")
            tz_name = "Asia/Shanghai"

        # Convert back to datetime for compatibility with _format_humanized_time
        local_dt_native = local_dt.naive()
        tzinfo = ZoneInfo(tz_name)
        local_dt_aware = local_dt_native.replace(tzinfo=tzinfo)

        return _format_humanized_time(local_dt_aware, tzinfo)
    except Exception:
        return None


def _format_humanized_time(dt: datetime, tzinfo: ZoneInfo) -> str:
    """
    Format datetime with humanized relative time description using Pendulum.

    Args:
        dt: Datetime to format (already in target timezone)
        tzinfo: Timezone info for calculating "now"

    Returns:
        Humanized time string like "今天17:19", "昨天17:19", "[11-18(五天前) 17:19]"
    """
    # Convert to Pendulum for easier manipulation
    pdt: PendulumDateTime = pendulum.instance(dt)
    now: PendulumDateTime = pendulum.now(str(tzinfo))

    # Get formatted components
    time_str = pdt.format("HH:mm")
    date_str = pdt.format("MM-DD")

    pdt_date = pdt.date()
    if pdt_date == now.date():
        return f"今天{time_str}"

    if pdt_date == now.subtract(days=1).date():
        return f"昨天{time_str}"

    # Calculate days difference
    days_diff = now.diff(pdt).in_days()

    # Within a week (2-6 days ago)
    if _DAYS_IN_WEEK_START <= days_diff <= _DAYS_IN_WEEK_END:
        relative = pdt.diff_for_humans(now, locale="zh")
        return f"{date_str}({relative}) {time_str}"

    # Within a month (7-30 days ago)
    if _DAYS_IN_MONTH_START <= days_diff <= _DAYS_IN_MONTH_END:
        relative = pdt.diff_for_humans(now, locale="zh")
        return f"{date_str}({relative}) {time_str}"

    # Within a year (31-364 days ago)
    if _DAYS_IN_YEAR_START <= days_diff < _DAYS_IN_YEAR:
        relative = pdt.diff_for_humans(now, locale="zh")
        return f"{date_str}({relative}) {time_str}"

    # More than a year ago
    relative = pdt.diff_for_humans(now, locale="zh")
    return f"{pdt.year}-{pdt.month:02d}-{pdt.day:02d}({relative}) {time_str}"


async def format_score_placeholders(db: AsyncSession, instance_id: int, template: str) -> str:
    """
    Format score-related placeholders in template.

    Handles placeholders like {{score:dimension_name}} by replacing them
    with current score values.

    Args:
        db: Database session
        instance_id: Instance ID
        template: Template string with score placeholders

    Returns:
        Template with score placeholders replaced

    Raises:
        AIServiceError: If score formatting fails
    """
    try:
        # Find all score placeholders in format {{score:dimension_name}}
        score_pattern = r"\{\{score:([^}]+)\}\}"
        score_matches = re.findall(score_pattern, template)

        if not score_matches:
            # No score placeholders found
            return template

        # Get current scores for the instance
        scores = await get_relationship_scores(db, instance_id)
        if not scores:
            logger.warning(
                "no_scores_found_for_placeholder_formatting",
                instance_id=instance_id,
            )
            # Replace all score placeholders with empty string
            return re.sub(score_pattern, "", template)

        # Build score lookup dictionary
        score_lookup = {score["dimension_name"]: score["score"] for score in scores}

        # Replace each score placeholder
        result = template
        replaced_count = 0

        for dimension_name in score_matches:
            placeholder = f"{{{{score:{dimension_name}}}}}"
            score_value = score_lookup.get(dimension_name)

            if score_value is not None:
                result = result.replace(placeholder, str(score_value))
                replaced_count += 1
            else:
                # Dimension not found, replace with empty string
                result = result.replace(placeholder, "")
                logger.warning(
                    "score_dimension_not_found_for_placeholder",
                    instance_id=instance_id,
                    dimension_name=dimension_name,
                )

        logger.debug(
            "score_placeholders_formatted",
            instance_id=instance_id,
            placeholders_found=len(score_matches),
            placeholders_replaced=replaced_count,
        )

    except Exception as e:
        logger.error(
            "score_placeholder_formatting_failed",
            error=str(e),
            instance_id=instance_id,
            exc_info=True,
        )
        raise AIServiceError(
            ai_service="placeholder_formatting",
            reason="formatting_failed",
            message=f"Failed to format score placeholders: {e!s}",
        ) from e

    return result


def validate_prompt_completeness(
    prompt: str, required_placeholders: list[str] | None = None
) -> dict[str, Any]:
    """
    Validate prompt completeness by checking for unresolved placeholders.

    Args:
        prompt: The prompt string to validate
        required_placeholders: List of required placeholder names (optional)

    Returns:
        Dictionary containing validation results:
        - is_valid: bool - Whether the prompt is valid
        - missing_placeholders: List[str] - List of missing required placeholders
        - unresolved_placeholders: List[str] - List of unresolved placeholders
        - warnings: List[str] - List of validation warnings
    """
    try:
        validation_result: dict[str, Any] = {
            "is_valid": True,
            "missing_placeholders": [],
            "unresolved_placeholders": [],
            "warnings": [],
        }

        # Find all unresolved placeholders (still in {{}} format)
        placeholder_pattern = r"\{\{([^}]+)\}\}"
        unresolved_matches = re.findall(placeholder_pattern, prompt)

        if unresolved_matches:
            validation_result["unresolved_placeholders"] = unresolved_matches
            validation_result["is_valid"] = False
            placeholders_str = ", ".join(unresolved_matches)
            validation_result["warnings"].append(
                f"Found {len(unresolved_matches)} unresolved placeholders: {placeholders_str}"
            )

        # Check for required placeholders if specified
        if required_placeholders:
            for required_placeholder in required_placeholders:
                placeholder_pattern = f"{{{{{required_placeholder}}}}}"
                if placeholder_pattern in prompt:
                    validation_result["missing_placeholders"].append(required_placeholder)
                    validation_result["is_valid"] = False

        # Check for empty or very short prompts
        if not prompt or len(prompt.strip()) < _MIN_PROMPT_LENGTH:
            validation_result["is_valid"] = False
            validation_result["warnings"].append("Prompt is empty or too short")

        # Check for common issues
        if "{{" in prompt and "}}" in prompt:
            # Additional check for malformed placeholders
            malformed_pattern = r"\{\{[^}]*\{\{|\}\}[^{]*\}\}"
            malformed_matches = re.findall(malformed_pattern, prompt)
            if malformed_matches:
                validation_result["warnings"].append(
                    f"Found potentially malformed placeholders: {', '.join(malformed_matches)}"
                )

        logger.debug(
            "prompt_validation_completed",
            prompt_length=len(prompt),
            is_valid=validation_result["is_valid"],
            unresolved_count=len(validation_result["unresolved_placeholders"]),
            missing_count=len(validation_result["missing_placeholders"]),
            warnings_count=len(validation_result["warnings"]),
        )

    except Exception as e:
        logger.error("prompt_validation_failed", error=str(e), exc_info=True)
        return {
            "is_valid": False,
            "missing_placeholders": [],
            "unresolved_placeholders": [],
            "warnings": [f"Validation failed: {e!s}"],
        }

    return validation_result
