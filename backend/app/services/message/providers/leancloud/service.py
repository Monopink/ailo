"""
LeanCloud message service business logic.

This module provides pure functions for LeanCloud service operations.
Functions orchestrate API calls and database operations.
"""

import secrets
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from services.config import config_service
from crud.system import system_configs
from .client import (
    create_system_conversation,
    subscribe_user_to_conversation,
    unsubscribe_user_from_conversation,
)
from .health import check_leancloud_health
from ..base import MessageData, MessageResult
from utils.logging import get_logger

logger = get_logger(__name__)


async def initialize_service(db: AsyncSession) -> bool:
    """
    Initialize LeanCloud message service.

    Creates system conversation if not exists and stores conversation_id in system_configs.

    Args:
        db: Database session for configuration access

    Returns:
        True if initialization successful, False otherwise

    Process:
        1. Get LeanCloud configuration from system_configs
        2. Check if system conversation ID exists
        3. If not exists, create system conversation via API
        4. Store conversation_id in system_configs
        5. Handle errors appropriately
    """
    try:
        # Get LeanCloud configuration
        leancloud_config = await config_service.get_leancloud_config(db)

        # Check if required configuration is available
        app_id = leancloud_config.get("app_id")
        master_key = leancloud_config.get("master_key")
        base_url = leancloud_config.get("base_url")

        if not app_id or not master_key or not base_url:
            logger.error(
                "leancloud_config_incomplete",
                has_app_id=bool(app_id),
                has_master_key=bool(master_key),
                has_base_url=bool(base_url),
            )
            return False

        # Check if system conversation ID already exists
        existing_conv_id = await system_configs.get_config_value(
            db, config_key="leancloud_service_conversation_id"
        )

        if existing_conv_id:
            logger.info("leancloud_system_conversation_exists", conversation_id=existing_conv_id)

            # Also check and generate webhook token if needed
            existing_webhook_token = await system_configs.get_config_value(
                db, config_key="leancloud_webhook_token"
            )

            if not existing_webhook_token:
                webhook_token = secrets.token_urlsafe(32)
                updated_token_config = await system_configs.update_config_value(
                    db,
                    config_key="leancloud_webhook_token",
                    config_value=webhook_token,
                    validate_enum=False,
                )

                if updated_token_config:
                    logger.info("leancloud_webhook_token_generated", token_length=len(webhook_token))
                else:
                    logger.warning("leancloud_webhook_token_generation_failed")

            return True

        # Create system conversation
        logger.info("leancloud_creating_system_conversation")
        success, conversation_id, error_msg = await create_system_conversation(
            app_id=app_id, master_key=master_key, base_url=base_url, name="系统对话"
        )

        if not success:
            logger.error("leancloud_system_conversation_creation_failed", error=error_msg)
            return False

        # Store conversation_id in system_configs
        updated_config = await system_configs.update_config_value(
            db,
            config_key="leancloud_service_conversation_id",
            config_value=conversation_id,
            validate_enum=False,
        )

        if not updated_config:
            logger.error("leancloud_failed_to_store_conversation_id", conversation_id=conversation_id)
            return False

        logger.info("leancloud_service_initialized", conversation_id=conversation_id)

        # Generate webhook token if not exists
        existing_webhook_token = await system_configs.get_config_value(
            db, config_key="leancloud_webhook_token"
        )

        if not existing_webhook_token:
            # Generate 43-character URL-safe token
            webhook_token = secrets.token_urlsafe(32)

            # Store token in system_configs
            updated_token_config = await system_configs.update_config_value(
                db, config_key="leancloud_webhook_token", config_value=webhook_token, validate_enum=False
            )

            if updated_token_config:
                logger.info("leancloud_webhook_token_generated", token_length=len(webhook_token))
            else:
                logger.warning("leancloud_webhook_token_generation_failed")
        else:
            logger.info("leancloud_webhook_token_exists", token_length=len(existing_webhook_token))

        return True

    except Exception as e:
        logger.error("leancloud_initialize_service_error", error=str(e), error_type=type(e).__name__)
        return False


async def refresh_system_conversation(db: AsyncSession) -> tuple[bool, Optional[str]]:
    """
    Refresh system conversation (create new one and update config).

    This function creates a new system conversation and updates the stored conversation_id.
    Used when the old conversation needs to be replaced.

    Args:
        db: Database session

    Returns:
        Tuple of (success, conversation_id_or_error_message)
        - If success=True: returns (True, new_conversation_id)
        - If success=False: returns (False, error_message)
    """
    try:
        # Get LeanCloud configuration
        leancloud_config = await config_service.get_leancloud_config(db)

        app_id = leancloud_config.get("app_id")
        master_key = leancloud_config.get("master_key")
        base_url = leancloud_config.get("base_url")

        if not app_id or not master_key or not base_url:
            error_msg = "LeanCloud configuration incomplete"
            logger.error("leancloud_config_incomplete_for_refresh")
            return False, error_msg

        # Create new system conversation
        logger.info("leancloud_refreshing_system_conversation")
        success, conversation_id, error_msg = await create_system_conversation(
            app_id=app_id, master_key=master_key, base_url=base_url, name="系统对话"
        )

        if not success:
            logger.error("leancloud_refresh_conversation_creation_failed", error=error_msg)
            return False, error_msg

        # Update conversation_id in system_configs
        updated_config = await system_configs.update_config_value(
            db,
            config_key="leancloud_service_conversation_id",
            config_value=conversation_id,
            validate_enum=False,
        )

        if not updated_config:
            error_msg = "Failed to update conversation_id in database"
            logger.error("leancloud_failed_to_update_conversation_id", conversation_id=conversation_id)
            return False, error_msg

        logger.info("leancloud_system_conversation_refreshed", new_conversation_id=conversation_id)
        return True, conversation_id

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(
            "leancloud_refresh_system_conversation_error", error=str(e), error_type=type(e).__name__
        )
        return False, error_msg


async def initialize_user(qiao_id: str, db: AsyncSession) -> bool:
    """
    Initialize user for LeanCloud message service.

    Subscribes user to system conversation.

    Args:
        qiao_id: User's qiao_id (maps to LeanCloud client_id)
        db: Database session

    Returns:
        True if initialization successful, False otherwise
    """
    try:
        # Get LeanCloud configuration
        leancloud_config = await config_service.get_leancloud_config(db)

        app_id = leancloud_config.get("app_id")
        master_key = leancloud_config.get("master_key")
        base_url = leancloud_config.get("base_url")
        conversation_id = leancloud_config.get("service_conversation_id")

        if not all([app_id, master_key, base_url, conversation_id]):
            logger.error("leancloud_config_incomplete_for_user_init", qiao_id=qiao_id)
            return False

        # Subscribe user to system conversation
        success, error_msg = await subscribe_user_to_conversation(
            app_id=app_id,
            master_key=master_key,
            base_url=base_url,
            conversation_id=conversation_id,
            client_id=qiao_id,
        )

        if not success:
            logger.error("leancloud_user_initialization_failed", qiao_id=qiao_id, error=error_msg)
            return False

        logger.info("leancloud_user_initialized", qiao_id=qiao_id)
        return True

    except Exception as e:
        logger.error(
            "leancloud_initialize_user_error", qiao_id=qiao_id, error=str(e), error_type=type(e).__name__
        )
        return False


async def deinitialize_user(qiao_id: str, db: AsyncSession) -> bool:
    """
    Clean up user's LeanCloud message service state.

    Unsubscribes user from system conversation.

    Args:
        qiao_id: User's qiao_id (maps to LeanCloud client_id)
        db: Database session

    Returns:
        True if cleanup successful, False otherwise
    """
    try:
        # Get LeanCloud configuration
        leancloud_config = await config_service.get_leancloud_config(db)

        app_id = leancloud_config.get("app_id")
        master_key = leancloud_config.get("master_key")
        base_url = leancloud_config.get("base_url")
        conversation_id = leancloud_config.get("service_conversation_id")

        if not all([app_id, master_key, base_url, conversation_id]):
            logger.error("leancloud_config_incomplete_for_user_deinit", qiao_id=qiao_id)
            return False

        # Unsubscribe user from system conversation
        success, error_msg = await unsubscribe_user_from_conversation(
            app_id=app_id,
            master_key=master_key,
            base_url=base_url,
            conversation_id=conversation_id,
            client_id=qiao_id,
        )

        if not success:
            logger.error("leancloud_user_deinitialization_failed", qiao_id=qiao_id, error=error_msg)
            return False

        logger.info("leancloud_user_deinitialized", qiao_id=qiao_id)
        return True

    except Exception as e:
        logger.error(
            "leancloud_deinitialize_user_error", qiao_id=qiao_id, error=str(e), error_type=type(e).__name__
        )
        return False


# Placeholder functions for future implementation


async def send_message(
    conversation_id: str, from_qiao_id: str, to_qiao_id: str, content: str, message_type: int = 1
) -> MessageResult:
    """Send single message through LeanCloud (to be implemented)."""
    return MessageResult(
        success=False,
        error_code="NOT_IMPLEMENTED",
        error_message="LeanCloud send_message not yet implemented",
    )


async def broadcast_message(
    conversation_id: str, from_qiao_id: str, to_qiao_ids: List[str], content: str, message_type: int = 1
) -> MessageResult:
    """Broadcast message through LeanCloud (to be implemented)."""
    return MessageResult(
        success=False,
        error_code="NOT_IMPLEMENTED",
        error_message="LeanCloud broadcast_message not yet implemented",
    )


async def fetch_messages_by_time_range(
    conversation_id: str, start_time: int, end_time: int, limit: int = 1000, include_start: bool = False
) -> List[MessageData]:
    """Fetch messages by time range from LeanCloud (to be implemented)."""
    return []


async def check_users_online(qiao_ids: List[str]) -> Dict[str, bool]:
    """Check users online status in LeanCloud (to be implemented)."""
    return {qiao_id: False for qiao_id in qiao_ids}


async def check_health(db: AsyncSession) -> tuple[bool, Optional[str]]:
    """
    Check LeanCloud service health.

    Verifies that the LeanCloud service is accessible and functioning correctly
    by making a lightweight API call to the /1.1/date endpoint.

    Args:
        db: Database session for configuration access

    Returns:
        Tuple of (is_healthy, error_message)
        - is_healthy: True if service is healthy and accessible
        - error_message: Error description if unhealthy, None if healthy

    Example:
        >>> is_healthy, error = await check_health(db)
        >>> if not is_healthy:
        ...     logger.error("LeanCloud service unhealthy", error=error)
    """
    try:
        # Get LeanCloud configuration
        leancloud_config = await config_service.get_leancloud_config(db)

        app_id = leancloud_config.get("app_id")
        master_key = leancloud_config.get("master_key")
        base_url = leancloud_config.get("base_url")

        # Validate configuration
        if not all([app_id, master_key, base_url]):
            missing_fields = []
            if not app_id:
                missing_fields.append("app_id")
            if not master_key:
                missing_fields.append("master_key")
            if not base_url:
                missing_fields.append("base_url")

            error_msg = f"LeanCloud configuration incomplete: missing {', '.join(missing_fields)}"
            logger.warning("leancloud_config_incomplete", missing_fields=missing_fields)
            return False, error_msg

        # Perform health check
        return await check_leancloud_health(app_id=app_id, master_key=master_key, base_url=base_url)

    except Exception as e:
        error_msg = f"Health check failed: {str(e)}"
        logger.error(
            "leancloud_health_check_error", error=str(e), error_type=type(e).__name__, exc_info=True
        )
        return False, error_msg
