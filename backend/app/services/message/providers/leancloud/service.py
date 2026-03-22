"""
LeanCloud message service business logic.

This module provides pure functions for LeanCloud service operations.
Functions orchestrate API calls and database operations.
"""

import secrets
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.system import system_configs
from app.enums import MessageType
from app.services.message.providers.base import MessageResult
from app.services.message.providers.leancloud.adapter import build_outbound_typed_message
from app.services.message.providers.leancloud.client import (
    check_service_conversation_exists,
    create_system_conversation,
    send_service_message,
    subscribe_user_to_conversation,
    unsubscribe_user_from_conversation,
)
from app.services.message.providers.leancloud.config import get_leancloud_runtime_config
from app.services.message.providers.leancloud.health import check_leancloud_health
from app.services.system_config import SystemConfigService, get_config
from app.type_defs import JSONDict
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

if TYPE_CHECKING:
    from app.services.message.schemas import InboundMessageEvent

logger = get_logger(__name__)


def _get_non_empty_str(value: Any) -> str | None:
    """Return the value if it is a non-empty string, otherwise None."""
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _get_non_empty_str(value)
    return _get_non_empty_str(str(value))


async def ensure_system_conversation(db: AsyncSession, existing_conv_id: str | None = None) -> str:
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
    leancloud_config = await get_leancloud_runtime_config(db, required=False)
    app_id = _get_non_empty_str(leancloud_config.app_id)
    master_key = _get_non_empty_str(leancloud_config.master_key)
    base_url = _get_non_empty_str(leancloud_config.base_url)

    if app_id is None or master_key is None or base_url is None:
        logger.error("leancloud_config_incomplete_for_ensure")
        raise ValueError("LeanCloud configuration incomplete")

    stored_conv_id = await get_config(
        db, key="leancloud_im_service_conversation_id", required=False
    )
    conversation_id = _get_non_empty_str(
        existing_conv_id
        or (
            stored_conv_id
            if isinstance(stored_conv_id, str)
            else (str(stored_conv_id) if stored_conv_id is not None else "")
        )
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
        leancloud_config = await get_leancloud_runtime_config(db, required=False)

        # Check if required configuration is available
        app_id = _get_non_empty_str(leancloud_config.app_id)
        master_key = _get_non_empty_str(leancloud_config.master_key)
        base_url = _get_non_empty_str(leancloud_config.base_url)

        if app_id is None or master_key is None or base_url is None:
            logger.error(
                "leancloud_config_incomplete",
                has_app_id=bool(app_id),
                has_master_key=bool(master_key),
                has_base_url=bool(base_url),
            )
            return False

        # Check if system conversation ID already exists
        existing_conv_id_value = await get_config(
            db, key="leancloud_im_service_conversation_id", required=False
        )
        existing_conv_id = _coerce_optional_str(existing_conv_id_value)

        if existing_conv_id:
            logger.info("leancloud_system_conversation_exists", conversation_id=existing_conv_id)

            # Also check and generate webhook token if needed
            existing_webhook_token_value = await get_config(
                db, key="leancloud_im_webhook_token", required=False
            )
            existing_webhook_token = _coerce_optional_str(existing_webhook_token_value)

            if not existing_webhook_token:
                webhook_token = secrets.token_urlsafe(18)
                updated_token_config = await system_configs.update_config_value(
                    db,
                    config_key="leancloud_im_webhook_token",
                    config_value=webhook_token,
                    validate_enum=False,
                )

                if updated_token_config:
                    logger.info(
                        "leancloud_webhook_token_generated", token_length=len(webhook_token)
                    )
                    await SystemConfigService.reload_cache(db)
                else:
                    logger.warning("leancloud_webhook_token_generation_failed")

            return True

        # Create system conversation
        logger.info("leancloud_creating_system_conversation")
        success, conversation_id_nullable, error_msg = await create_system_conversation(
            app_id=app_id, master_key=master_key, base_url=base_url, name="uni_conversation_id"
        )

        # Complete type guard: check both success flag and conversation_id
        if not success or conversation_id_nullable is None:
            logger.error(
                "leancloud_system_conversation_creation_failed",
                success=success,
                has_conversation_id=conversation_id_nullable is not None,
                error=error_msg,
            )
            return False

        # Type narrowing: conversation_id_nullable is now guaranteed to be str
        conversation_id: str = conversation_id_nullable

        # Store conversation_id in system_configs
        updated_config = await system_configs.update_config_value(
            db,
            config_key="leancloud_im_service_conversation_id",
            config_value=conversation_id,
            validate_enum=False,
        )

        if not updated_config:
            logger.error(
                "leancloud_failed_to_store_conversation_id", conversation_id=conversation_id
            )
            return False

        await SystemConfigService.reload_cache(db)

        logger.info("leancloud_service_initialized", conversation_id=conversation_id)

        # Generate webhook token if not exists
        existing_webhook_token_value = await get_config(
            db, key="leancloud_im_webhook_token", required=False
        )
        existing_webhook_token = _coerce_optional_str(existing_webhook_token_value)

        if not existing_webhook_token:
            # Generate 24-character URL-safe token
            webhook_token = secrets.token_urlsafe(18)

            # Store token in system_configs
            updated_token_config = await system_configs.update_config_value(
                db,
                config_key="leancloud_im_webhook_token",
                config_value=webhook_token,
                validate_enum=False,
            )

            if updated_token_config:
                logger.info("leancloud_webhook_token_generated", token_length=len(webhook_token))
                await SystemConfigService.reload_cache(db)
            else:
                logger.warning("leancloud_webhook_token_generation_failed")
        else:
            token_length = len(str(existing_webhook_token))
            logger.info("leancloud_webhook_token_exists", token_length=token_length)

        return True

    except Exception as e:
        logger.error(
            "leancloud_initialize_service_error", error=str(e), error_type=type(e).__name__
        )
        return False


async def refresh_system_conversation(db: AsyncSession) -> tuple[bool, str | None]:
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
        leancloud_config = await get_leancloud_runtime_config(db, required=False)

        app_id = _get_non_empty_str(leancloud_config.app_id)
        master_key = _get_non_empty_str(leancloud_config.master_key)
        base_url = _get_non_empty_str(leancloud_config.base_url)

        if app_id is None or master_key is None or base_url is None:
            error_msg = "LeanCloud configuration incomplete"
            logger.error("leancloud_config_incomplete_for_refresh")
            return False, error_msg

        # Create new system conversation
        logger.info("leancloud_refreshing_system_conversation")
        success: bool
        conversation_id_nullable: str | None
        create_error_msg: str | None
        success, conversation_id_nullable, create_error_msg = await create_system_conversation(
            app_id=app_id, master_key=master_key, base_url=base_url, name="uni_conversation_id"
        )

        # Complete type guard: check both success flag and conversation_id
        if not success or conversation_id_nullable is None:
            logger.error(
                "leancloud_refresh_conversation_creation_failed",
                success=success,
                has_conversation_id=conversation_id_nullable is not None,
                error=create_error_msg,
            )
            return False, create_error_msg

        # Type narrowing: conversation_id_nullable is now guaranteed to be str
        conversation_id: str = conversation_id_nullable

        # Update conversation_id in system_configs
        updated_config = await system_configs.update_config_value(
            db,
            config_key="leancloud_im_service_conversation_id",
            config_value=conversation_id,
            validate_enum=False,
        )

        if not updated_config:
            error_msg = "Failed to update conversation_id in database"
            logger.error(
                "leancloud_failed_to_update_conversation_id", conversation_id=conversation_id
            )
            return False, error_msg

        await SystemConfigService.reload_cache(db)

        logger.info("leancloud_system_conversation_refreshed", new_conversation_id=conversation_id)
        return True, conversation_id

    except Exception as e:
        error_msg = f"Unexpected error: {e!s}"
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
        leancloud_config = await get_leancloud_runtime_config(db, required=False)

        app_id = _get_non_empty_str(leancloud_config.app_id)
        master_key = _get_non_empty_str(leancloud_config.master_key)
        base_url = _get_non_empty_str(leancloud_config.base_url)
        conversation_id_value = await get_config(
            db, key="leancloud_im_service_conversation_id", required=False
        )
        conversation_id = _coerce_optional_str(conversation_id_value)

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
            "leancloud_initialize_user_error",
            qiao_id=qiao_id,
            error=str(e),
            error_type=type(e).__name__,
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
        leancloud_config = await get_leancloud_runtime_config(db, required=False)

        app_id = _get_non_empty_str(leancloud_config.app_id)
        master_key = _get_non_empty_str(leancloud_config.master_key)
        base_url = _get_non_empty_str(leancloud_config.base_url)
        conversation_id_value = await get_config(
            db, key="leancloud_im_service_conversation_id", required=False
        )
        conversation_id = _coerce_optional_str(conversation_id_value)

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
            "leancloud_deinitialize_user_error",
            qiao_id=qiao_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return False


async def _load_send_config(db: AsyncSession) -> tuple[str, str, str, str] | None:
    """Load LeanCloud send configuration."""
    leancloud_config = await get_leancloud_runtime_config(db, required=False)
    app_id = _get_non_empty_str(leancloud_config.app_id)
    master_key = _get_non_empty_str(leancloud_config.master_key)
    base_url = _get_non_empty_str(leancloud_config.base_url)
    lc_conv_id_value = await get_config(
        db, key="leancloud_im_service_conversation_id", required=False
    )
    lc_conv_id = _coerce_optional_str(lc_conv_id_value)
    if app_id is None or master_key is None or base_url is None or lc_conv_id is None:
        return None
    return app_id, master_key, base_url, lc_conv_id


async def send_message_to_client(
    db: AsyncSession,
    *,
    target_client_id: str,
    from_qiao_id: str,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int = MessageType.TEXT,
    action: JSONDict | None = None,
    extra_fields: JSONDict | None = None,
    msg_id: str | None = None,
    supports_typing: bool = True,
    transient: bool | None = None,
) -> MessageResult:
    """Send one message to one LeanCloud client id (endpoint-level send)."""
    try:
        config = await _load_send_config(db)
        if config is None:
            return MessageResult(
                success=False,
                error_code="CONFIG_MISSING",
                error_message="LeanCloud configuration incomplete",
            )
        app_id, master_key, base_url, lc_conv_id = config

        message_json = build_outbound_typed_message(
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            conversation_id=conv_id,
            content=content,
            message_type=message_type,
            msg_id=msg_id or f"msg_{generate_snowflake_id()}",
            supports_typing=supports_typing,
            action=action,
            extra_fields=extra_fields,
        )

        success, provider_msg_id, error = await send_service_message(
            app_id=app_id,
            master_key=master_key,
            base_url=base_url,
            conversation_id=lc_conv_id,
            from_client=from_qiao_id,
            to_clients=[target_client_id],
            message=message_json,
            transient=transient,
        )
        if success:
            return MessageResult(success=True, msg_id_provider=provider_msg_id)
        return MessageResult(success=False, error_code="SEND_FAILED", error_message=error)
    except Exception as e:
        logger.error(
            "send_message_to_client_exception",
            error=str(e),
            from_qiao_id=from_qiao_id,
            target_client_id=target_client_id,
        )
        return MessageResult(success=False, error_code="EXCEPTION", error_message=str(e))


async def send_message(
    db: AsyncSession,
    from_qiao_id: str,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int = 1,
    extra_fields: JSONDict | None = None,
    msg_id: str | None = None,
) -> MessageResult:
    """Compatibility wrapper: recipient qiao_id is also target client id."""
    return await send_message_to_client(
        db,
        target_client_id=to_qiao_id,
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
        conv_id=conv_id,
        content=content,
        message_type=message_type,
        action=None,
        extra_fields=extra_fields,
        msg_id=msg_id,
        supports_typing=True,
    )


async def send_message_as_system(
    db: AsyncSession,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int = MessageType.CHAT_INFO,
    action: JSONDict | None = None,
    extra_fields: JSONDict | None = None,
    msg_id: str | None = None,
) -> MessageResult:
    """Send message as system through LeanCloud."""
    return await send_message_to_client(
        db,
        target_client_id=to_qiao_id,
        from_qiao_id="system",
        to_qiao_id=to_qiao_id,
        conv_id=conv_id,
        content=content,
        message_type=message_type,
        action=action,
        extra_fields=extra_fields,
        msg_id=msg_id,
        supports_typing=False,
    )


async def get_conversation_registry_state(db: AsyncSession) -> JSONDict:
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
    conversation_id: str,
    from_qiao_id: str,
    to_qiao_ids: list[str],
    content: str,
    message_type: int = 1,
) -> MessageResult:
    """Broadcast message through LeanCloud (to be implemented).

    Args:
        conversation_id: The LeanCloud conversation ID.
        from_qiao_id: Sender qiao_id.
        to_qiao_ids: Recipient qiao_id list.
        content: Message body.
        message_type: LeanCloud message type.

    Returns:
        MessageResult: Always indicates unimplemented behavior.
    """
    logger.warning(
        "leancloud_broadcast_message_skipped",
        conversation_id=conversation_id,
        from_qiao_id=from_qiao_id,
        to_recipient_count=len(to_qiao_ids),
        message_type=message_type,
        content_preview=content[:100],
    )
    return MessageResult(
        success=False,
        error_code="NOT_IMPLEMENTED",
        error_message=(
            "LeanCloud broadcast_message is not yet implemented "
            f"(conversation={conversation_id}, from={from_qiao_id}, type={message_type}) "
            f"content={content}"
        ),
    )


async def fetch_messages_by_time_range(
    conversation_id: str,
    start_time: int,
    end_time: int,
    limit: int = 1000,
    include_start: bool = False,
) -> list["InboundMessageEvent"]:
    """Fetch messages by time range from LeanCloud (to be implemented).

    Args:
        conversation_id: LeanCloud conversation ID.
        start_time: Range start timestamp (Unix seconds).
        end_time: Range end timestamp (Unix seconds).
        limit: Maximum number of messages to return.
        include_start: Whether to include the message at start_time.

    Returns:
        Placeholder inbox list (empty for now).
    """
    logger.warning(
        "leancloud_fetch_messages_placeholder",
        conversation_id=conversation_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        include_start=include_start,
    )
    return []


async def check_users_online(qiao_ids: list[str]) -> dict[str, bool]:
    """Check users online status in LeanCloud (to be implemented)."""
    return dict.fromkeys(qiao_ids, False)


async def check_health(db: AsyncSession) -> tuple[bool, str | None]:
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
        leancloud_config = await get_leancloud_runtime_config(db, required=False)

        app_id = _get_non_empty_str(leancloud_config.app_id)
        master_key = _get_non_empty_str(leancloud_config.master_key)
        base_url = _get_non_empty_str(leancloud_config.base_url)

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
        is_healthy, error_message = await check_leancloud_health(
            app_id=app_id,
            master_key=master_key,
            base_url=base_url,
        )
        return is_healthy, error_message

    except Exception as e:
        error_msg = f"Health check failed: {e!s}"
        logger.error(
            "leancloud_health_check_error", error=str(e), error_type=type(e).__name__, exc_info=True
        )
        return False, error_msg
