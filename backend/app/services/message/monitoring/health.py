"""
Message service health check.

Provides provider-agnostic health check functionality for the message service.
"""

from datetime import datetime
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from services.message.providers.leancloud import create_leancloud_provider
from utils.logging import get_logger

logger = get_logger(__name__)


async def check_message_service_health(db: AsyncSession) -> Dict[str, Any]:
    """
    Check message service health (provider-agnostic).

    This function checks the health of the currently configured message service provider.
    It returns a standardized health status that can be used for monitoring and alerting.

    Args:
        db: Database session for configuration access

    Returns:
        Dictionary containing:
        - healthy (bool): True if service is healthy
        - provider (str): Provider name (e.g., "leancloud")
        - error (str|None): Error message if unhealthy
        - checked_at (int): Timestamp in milliseconds

    Example:
        >>> health = await check_message_service_health(db)
        >>> if not health["healthy"]:
        ...     logger.error("Message service unhealthy", error=health["error"])
    """
    try:
        # Get current provider (currently only LeanCloud is implemented)
        # In the future, this could be configurable via system_configs
        provider = create_leancloud_provider(db)

        # Check health
        is_healthy, error_msg = await provider.check_health()

        result = {
            "healthy": is_healthy,
            "provider": "leancloud",
            "error": error_msg,
            "checked_at": int(datetime.utcnow().timestamp() * 1000),
        }

        if is_healthy:
            logger.debug("message_service_health_check_passed", provider="leancloud")
        else:
            logger.warning("message_service_health_check_failed", provider="leancloud", error=error_msg)

        return result

    except Exception as e:
        error_msg = f"Health check failed: {str(e)}"
        logger.error(
            "message_service_health_check_error", error=str(e), error_type=type(e).__name__, exc_info=True
        )

        return {
            "healthy": False,
            "provider": "unknown",
            "error": error_msg,
            "checked_at": int(datetime.utcnow().timestamp() * 1000),
        }


async def get_message_service_status(db: AsyncSession) -> Dict[str, Any]:
    """
    Get comprehensive message service status.

    This function provides more detailed status information than check_message_service_health,
    including configuration status and service initialization status.

    Args:
        db: Database session for configuration access

    Returns:
        Dictionary containing:
        - healthy (bool): Overall health status
        - provider (str): Provider name
        - error (str|None): Error message if any
        - checked_at (int): Timestamp in milliseconds
        - details (dict): Additional status details
            - config_complete (bool): Whether configuration is complete
            - service_initialized (bool): Whether service is initialized
            - api_accessible (bool): Whether API is accessible

    Example:
        >>> status = await get_message_service_status(db)
        >>> if not status["details"]["config_complete"]:
        ...     logger.error("Message service configuration incomplete")
    """
    try:
        from services.config import config_service
        from crud.system import system_configs

        # Check configuration completeness
        leancloud_config = await config_service.get_leancloud_config(db)
        config_complete = all(
            [
                leancloud_config.get("app_id"),
                leancloud_config.get("master_key"),
                leancloud_config.get("base_url"),
            ]
        )

        # Check service initialization
        conversation_id = await system_configs.get_config_value(
            db, config_key="leancloud_im_service_conversation_id"
        )
        service_initialized = bool(conversation_id)

        # Check API accessibility
        health_result = await check_message_service_health(db)
        api_accessible = health_result["healthy"]

        # Determine overall health
        overall_healthy = config_complete and service_initialized and api_accessible

        return {
            "healthy": overall_healthy,
            "provider": "leancloud",
            "error": health_result["error"] if not overall_healthy else None,
            "checked_at": health_result["checked_at"],
            "details": {
                "config_complete": config_complete,
                "service_initialized": service_initialized,
                "api_accessible": api_accessible,
            },
        }

    except Exception as e:
        error_msg = f"Status check failed: {str(e)}"
        logger.error(
            "message_service_status_check_error", error=str(e), error_type=type(e).__name__, exc_info=True
        )

        return {
            "healthy": False,
            "provider": "unknown",
            "error": error_msg,
            "checked_at": int(datetime.utcnow().timestamp() * 1000),
            "details": {"config_complete": False, "service_initialized": False, "api_accessible": False},
        }
