"""
AI instance retrieval and validation module.

This module handles instance information retrieval and validation
with clear error handling and single responsibility principle.
"""

from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from .queries import get_instance_context
from exceptions import AIInstanceNotFoundError, AIInstanceInactiveError
from utils.logging import get_logger
from services.ai.types import InstanceContext

logger = get_logger(__name__)


async def get_instance_info(db: AsyncSession, instance_qiao_id: str) -> InstanceContext:
    """
    Get instance information with validation.

    Args:
        db: Database session
        instance_qiao_id: Instance's qiao_id

    Returns:
        Dictionary containing instance information

    Raises:
        InstanceNotFoundError: If instance doesn't exist
        InstanceInactiveError: If instance is inactive or blocked
    """
    context = await get_instance_context(db, instance_qiao_id=instance_qiao_id)

    if not context:
        raise AIInstanceNotFoundError(instance_id=instance_qiao_id)

    instance_status = context["status"]
    if instance_status != 1:
        if instance_status == 2:
            raise AIInstanceInactiveError(
                instance_id=instance_qiao_id, status=instance_status, message="Instance is inactive"
            )
        elif instance_status == 3:
            raise AIInstanceInactiveError(
                instance_id=instance_qiao_id, status=instance_status, message="Instance is blocked"
            )
        else:
            raise AIInstanceInactiveError(
                instance_id=instance_qiao_id,
                status=instance_status,
                message=f"Instance has invalid status {instance_status}",
            )

    logger.debug(
        "instance_info_retrieved",
        instance_qiao_id=instance_qiao_id,
        personality_id=context["personality"]["id"],
        style_id=context["style"]["id"],
    )

    return context


async def validate_instance_status(instance: Any) -> None:
    """
    Validate instance status.

    Args:
        instance: Instance model instance

    Raises:
        InstanceInactiveError: If instance is not active
    """
    if instance.status != 1:  # 1 = active
        if instance.status == 2:
            raise AIInstanceInactiveError(
                instance_id=instance.qiao_id, status=instance.status, message="Instance is inactive"
            )
        elif instance.status == 3:
            raise AIInstanceInactiveError(
                instance_id=instance.qiao_id, status=instance.status, message="Instance is blocked"
            )
        else:
            raise AIInstanceInactiveError(
                instance_id=instance.qiao_id,
                status=instance.status,
                message=f"Instance has invalid status {instance.status}",
            )


async def get_instance_configuration(db: AsyncSession, instance_id: int) -> Dict[str, Any]:
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
        raise RuntimeError(f"Failed to get instance configuration: {str(e)}")
