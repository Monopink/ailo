"""
LeanCloud message service business logic.

This module provides pure functions for LeanCloud service operations.
Functions orchestrate API calls and database operations.
"""

import secrets
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from crud.system import system_configs
from enums import MessageType
from services.config import config_service
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger
from utils.snowflake import generate_snowflake_id

from ..base import MessageResult
from .adapter import build_outbound_typed_message
from .client import (
    check_service_conversation_exists,
    create_system_conversation,
    send_service_message,
    subscribe_user_to_conversation,
    unsubscribe_user_from_conversation,
)
from .health import check_leancloud_health

if TYPE_CHECKING:
    from services.message.schemas import InboundMessageEvent

logger = get_logger(__name__)


def _get_non_empty_str(value: Any) -> Optional[str]:
    """Return the value if it is a non-empty string, otherwise None."""
    if isinstance(value, str) and value:
        return value
    return None


async def ensure_system_conversation(db: AsyncSession, existing_conv_id: Optional[str] = None) -> str:
    """
    Ensure system conversation exists and is valid.

    Args:
        db: Database session
        existing_conv_id: Optional cached conversation ID

    Returns:
        Valid LeanCloud conversation ID

    Raises:
        ValueError: If conversation cannot be ensured
    """
    leancloud_config = await config_service.get_leancloud_config(db)
    app_id = _get_non_empty_str(leancloud_config.get("app_id"))
    master_key = _get_non_empty_str(leancloud_config.get("master_key"))
    base_url = _get_non_empty_str(leancloud_config.get("base_url"))

    if app_id is None or master_key is None or base_url is None:
        logger.error("leancloud_config_incomplete_for_ensure")
        raise ValueError("LeanCloud configuration incomplete")

    conversation_id = _get_non_empty_str(
        existing_conv_id
        or await system_configs.get_config_value(db, config_key="leancloud_im_service_conversation_id")
    )

    if conversation_id:
        try:
            exists, error_message = await check_service_conversation_exists(
                app_id=app_id,
                master_key=master_key,
                base_url=base_url,
                conversation_id=conversation_id,
            )
        except Exception as error:  # pragma: no cover - defensive logging
            logger.error(
                "leancloud_conversation_check_error",
                conversation_id=conversation_id,
                error=str(error),
            )
            exists = False
            error_message = str(error)

        if exists:
            return conversation_id

        logger.warning(
            "leancloud_conversation_invalid",
            conversation_id=conversation_id,
            error=error_message,
        )

    success, refreshed_conversation_id = await refresh_system_conversation(db)
    if success and refreshed_conversation_id:
        return refreshed_conversation_id

    raise ValueError("Failed to ensure LeanCloud system conversation")


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
        app_id = _get_non_empty_str(leancloud_config.get("app_id"))
        master_key = _get_non_empty_str(leancloud_config.get("master_key"))
        base_url = _get_non_empty_str(leancloud_config.get("base_url"))

        if app_id is None or master_key is None or base_url is None:
            logger.error(
                "leancloud_config_incomplete",
                has_app_id=bool(app_id),
                has_master_key=bool(master_key),
                has_base_url=bool(base_url),
            )
            return False

        # Check if system conversation ID already exists
        existing_conv_id = await system_configs.get_config_value(
            db, config_key="leancloud_im_service_conversation_id"
        )

        if existing_conv_id:
            logger.info("leancloud_system_conversation_exists", conversation_id=existing_conv_id)

            # Also check and generate webhook token if needed
            existing_webhook_token = await system_configs.get_config_value(
                db, config_key="leancloud_im_webhook_token"
            )

            if not existing_webhook_token:
                webhook_token = secrets.token_urlsafe(18)
                updated_token_config = await system_configs.update_config_value(
                    db,
                    config_key="leancloud_im_webhook_token",
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
            app_id=app_id, master_key=master_key, base_url=base_url, name="uni_conversation_id"
        )

        if not success:
            logger.error("leancloud_system_conversation_creation_failed", error=error_msg)
            return False

        # Store conversation_id in system_configs
        updated_config = await system_configs.update_config_value(
            db,
            config_key="leancloud_im_service_conversation_id",
            config_value=conversation_id,
            validate_enum=False,
        )

        if not updated_config:
            logger.error("leancloud_failed_to_store_conversation_id", conversation_id=conversation_id)
            return False

        logger.info("leancloud_service_initialized", conversation_id=conversation_id)

        # Generate webhook token if not exists
        existing_webhook_token = await system_configs.get_config_value(
            db, config_key="leancloud_im_webhook_token"
        )

        if not existing_webhook_token:
            # Generate 24-character URL-safe token
            webhook_token = secrets.token_urlsafe(18)

            # Store token in system_configs
            updated_token_config = await system_configs.update_config_value(
                db, config_key="leancloud_im_webhook_token", config_value=webhook_token, validate_enum=False
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

        app_id = _get_non_empty_str(leancloud_config.get("app_id"))
        master_key = _get_non_empty_str(leancloud_config.get("master_key"))
        base_url = _get_non_empty_str(leancloud_config.get("base_url"))

        if app_id is None or master_key is None or base_url is None:
            error_msg = "LeanCloud configuration incomplete"
            logger.error("leancloud_config_incomplete_for_refresh")
            return False, error_msg

        # Create new system conversation
        logger.info("leancloud_refreshing_system_conversation")
        success, conversation_id, error_msg = await create_system_conversation(
            app_id=app_id, master_key=master_key, base_url=base_url, name="uni_conversation_id"
        )

        if not success:
            logger.error("leancloud_refresh_conversation_creation_failed", error=error_msg)
            return False, error_msg

        # Update conversation_id in system_configs
        updated_config = await system_configs.update_config_value(
            db,
            config_key="leancloud_im_service_conversation_id",
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

        app_id = _get_non_empty_str(leancloud_config.get("app_id"))
        master_key = _get_non_empty_str(leancloud_config.get("master_key"))
        base_url = _get_non_empty_str(leancloud_config.get("base_url"))
        conversation_id = _get_non_empty_str(
            await system_configs.get_config_value(db, config_key="leancloud_im_service_conversation_id")
        )

        if app_id is None or master_key is None or base_url is None or conversation_id is None:
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

        app_id = _get_non_empty_str(leancloud_config.get("app_id"))
        master_key = _get_non_empty_str(leancloud_config.get("master_key"))
        base_url = _get_non_empty_str(leancloud_config.get("base_url"))
        conversation_id = _get_non_empty_str(
            await system_configs.get_config_value(db, config_key="leancloud_im_service_conversation_id")
        )

        if app_id is None or master_key is None or base_url is None or conversation_id is None:
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
    db: AsyncSession,
    from_qiao_id: str,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int = 1,
    extra_fields: Optional[dict] = None,
    msg_id: Optional[str] = None,
) -> MessageResult:
    """
    Send message through LeanCloud.

    Args:
        db: Database session for configuration access
        from_qiao_id: Sender's qiao_id
        to_qiao_id: Receiver's qiao_id
        conv_id: Internal conversation ID (included in message)
        content: Message content
        message_type: Message type (default: 1=TEXT)

    Returns:
        MessageResult with success status and message ID
    """
    try:
        # Get LeanCloud configuration
        leancloud_config = await config_service.get_leancloud_config(db)
        app_id = _get_non_empty_str(leancloud_config.get("app_id"))
        master_key = _get_non_empty_str(leancloud_config.get("master_key"))
        base_url = _get_non_empty_str(leancloud_config.get("base_url"))

        # Get LeanCloud IM system conversation ID
        lc_conv_id = _get_non_empty_str(
            await system_configs.get_config_value(db, config_key="leancloud_im_service_conversation_id")
        )

        if app_id is None or master_key is None or base_url is None or lc_conv_id is None:
            return MessageResult(
                success=False,
                error_code="CONFIG_MISSING",
                error_message="LeanCloud configuration incomplete",
            )

        # Construct message JSON
        message_json = build_outbound_typed_message(
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            conv_id=conv_id,
            content=content,
            message_type=message_type,
            msg_id=msg_id or f"msg_{generate_snowflake_id()}",
            supports_typing=True,
            extra_fields=extra_fields,
        )

        # Send message through LeanCloud API
        success, msg_id, error = await send_service_message(
            app_id=app_id,
            master_key=master_key,
            base_url=base_url,
            conversation_id=lc_conv_id,
            from_client=from_qiao_id,
            to_clients=[to_qiao_id],
            message=message_json,
        )

        if success:
            return MessageResult(success=True, msg_id_provider=msg_id)
        else:
            return MessageResult(success=False, error_code="SEND_FAILED", error_message=error)

    except Exception as e:
        logger.error(
            "send_message_exception", error=str(e), from_qiao_id=from_qiao_id, to_qiao_id=to_qiao_id
        )
        return MessageResult(success=False, error_code="EXCEPTION", error_message=str(e))


async def send_message_as_system(
    db: AsyncSession,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int = MessageType.CHAT_INFO,
    action: Optional[dict] = None,
    extra_fields: Optional[dict] = None,
    msg_id: Optional[str] = None,
) -> MessageResult:
    """
    Send message as system through LeanCloud.

    Messages sent as system use "system" as from_client.

    Args:
        db: Database session for configuration access
        to_qiao_id: Receiver's qiao_id
        conv_id: Internal conversation ID (included in message)
        content: Message content (already mapped by business layer)

    Returns:
        MessageResult with success status and message ID
    """
    try:
        # Get LeanCloud configuration
        leancloud_config = await config_service.get_leancloud_config(db)
        app_id = _get_non_empty_str(leancloud_config.get("app_id"))
        master_key = _get_non_empty_str(leancloud_config.get("master_key"))
        base_url = _get_non_empty_str(leancloud_config.get("base_url"))

        # Get LeanCloud IM system conversation ID
        lc_conv_id = _get_non_empty_str(
            await system_configs.get_config_value(db, config_key="leancloud_im_service_conversation_id")
        )

        if app_id is None or master_key is None or base_url is None or lc_conv_id is None:
            return MessageResult(
                success=False,
                error_code="CONFIG_MISSING",
                error_message="LeanCloud configuration incomplete",
            )

        # Construct message JSON
        message_json = build_outbound_typed_message(
            from_qiao_id="system",
            to_qiao_id=to_qiao_id,
            conv_id=conv_id,
            content=content,
            message_type=message_type,
            msg_id=msg_id or f"msg_{generate_snowflake_id()}",
            supports_typing=False,
            action=action,
            extra_fields=extra_fields,
        )

        # Send message as system through LeanCloud API
        success, msg_id, error = await send_service_message(
            app_id=app_id,
            master_key=master_key,
            base_url=base_url,
            conversation_id=lc_conv_id,
            from_client="system",  # Messages sent as system use "system" as sender
            to_clients=[to_qiao_id],
            message=message_json,
        )

        if success:
            return MessageResult(success=True, msg_id_provider=msg_id)
        else:
            return MessageResult(success=False, error_code="SEND_FAILED", error_message=error)

    except Exception as e:
        logger.error("send_message_as_system_exception", error=str(e), to_qiao_id=to_qiao_id)
        return MessageResult(success=False, error_code="EXCEPTION", error_message=str(e))


async def get_conversation_registry_state(db: AsyncSession) -> dict:
    """
    Get the current LeanCloud conversation registry state.

    Returns:
        dict with im_conv_id only
    """
    im_conv_id = await ensure_system_conversation(db)
    return {
        "im_conv_id": im_conv_id,
    }


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
) -> List["InboundMessageEvent"]:
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

        app_id = _get_non_empty_str(leancloud_config.get("app_id"))
        master_key = _get_non_empty_str(leancloud_config.get("master_key"))
        base_url = _get_non_empty_str(leancloud_config.get("base_url"))

        # Validate configuration
        if app_id is None or master_key is None or base_url is None:
            missing_fields = []
            if app_id is None:
                missing_fields.append("app_id")
            if master_key is None:
                missing_fields.append("master_key")
            if base_url is None:
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
