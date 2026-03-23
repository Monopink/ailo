"""
AI instance retrieval and validation module.

This module handles instance information retrieval and validation with clear
error handling and single responsibility principle.
"""

from typing import NoReturn

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import AIInstanceStatus
from app.exceptions import AIInstanceInactiveError, AIInstanceNotFoundError
from app.models.ai.instance import AIInstance
from app.type_defs import InstanceContext, JSONDict
from app.utils.logging import get_logger

from .queries import get_instance_context

logger = get_logger(__name__)


def _raise_inactive_error(instance_id: str, status_code: int | None, message: str) -> NoReturn:
    raise AIInstanceInactiveError(
        instance_id=instance_id,
        status=status_code if status_code is not None else -1,
        message=message,
    )


def _as_instance_status(value: int | None) -> AIInstanceStatus | None:
    if value is None:
        return None
    try:
        return AIInstanceStatus(value)
    except ValueError:
        return None


def _ensure_active(
    instance_id: str,
    status_code: int | None,
    status: AIInstanceStatus | None,
) -> None:
    if status == AIInstanceStatus.ACTIVE:
        return
    if status == AIInstanceStatus.INACTIVE:
        _raise_inactive_error(instance_id, status.value, "Instance is inactive")
    if status == AIInstanceStatus.BLOCKED:
        _raise_inactive_error(instance_id, status.value, "Instance is blocked")
    _raise_inactive_error(
        instance_id,
        status_code,
        f"Instance has invalid status {status_code}",
    )


async def get_instance_info(
    db: AsyncSession, instance_qiao_id: str, user_qiao_id: str
) -> InstanceContext:
    """
    Get instance information with validation.

    Args:
        db: Database session
        instance_qiao_id: Instance's qiao_id
        user_qiao_id: User's qiao_id

    Returns:
        Dictionary containing instance information

    Raises:
        InstanceNotFoundError: If instance doesn't exist
        InstanceInactiveError: If instance is inactive or blocked
    """
    context = await get_instance_context(
        db, instance_qiao_id=instance_qiao_id, user_qiao_id=user_qiao_id
    )

    if not context:
        raise AIInstanceNotFoundError(instance_id=instance_qiao_id)

    status_value = context.get("status")
    status = _as_instance_status(status_value if isinstance(status_value, int) else None)
    _ensure_active(
        instance_id=instance_qiao_id,
        status_code=status_value if isinstance(status_value, int) else None,
        status=status,
    )

    logger.debug(
        "instance_info_retrieved",
        instance_qiao_id=instance_qiao_id,
        personality_id=context["personality"]["id"],
        style_id=context["style"]["id"],
    )

    return context


async def validate_instance_status(instance: AIInstance) -> None:
    """
    Validate instance status.

    Args:
        instance: Instance model instance

    Raises:
        InstanceInactiveError: If instance is not active
    """
    status_value = instance.status
    status = _as_instance_status(status_value)
    _ensure_active(
        instance_id=instance.qiao_id,
        status_code=status_value,
        status=status,
    )


async def get_instance_configuration(_db: AsyncSession, instance_id: int) -> JSONDict:
    """
    Get instance configuration including personality and style.

    Args:
        db: Database session
        instance_id: Instance ID

    Returns:
        Dictionary containing instance configuration

    Raises:
        RuntimeError: If configuration retrieval fails
    """
    try:
        # This function needs to be implemented to get instance configuration
        # For now, this is a placeholder implementation
        logger.debug("instance_configuration_requested", instance_id=instance_id)

        return {
            "instance_id": instance_id,
            "personality": None,  # Would be populated with actual data
            "style": None,  # Would be populated with actual data
            "placeholders": {},
            "relationship_mappings": [],
        }

    except Exception as e:
        logger.error("instance_configuration_failed", error=str(e), instance_id=instance_id)
        raise RuntimeError(f"Failed to get instance configuration: {e!s}")
