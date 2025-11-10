"""
Message sending service (business layer).

Handles outgoing messages without concerning transport protocol details.
Provider layer handles protocol-specific fields like from_client.
"""

import time
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from enums import MessageType
from services.message.providers.factory import get_default_provider
from services.message.storage.persistence import store_message as store_message_to_db
from services.message.security.encryption import encrypt_for_transport
from services.message.schemas import EventMetadata, OutboundMessageEvent, ProviderMetadata
from utils.snowflake import generate_snowflake_id
from crud.message import notification_push_history as notification_crud
from utils.logging import get_logger

logger = get_logger(__name__)


async def _send_message_internal(
    db: AsyncSession,
    *,
    from_qiao_id: str,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int,
    action: Optional[dict] = None,
    extra_fields: Optional[dict] = None,
    msg_id: Optional[str] = None,
) -> tuple["MessageResult", Dict[str, Any]]:
    """
    Internal message sending function.

    This is a private function that handles the actual message sending
    through the provider layer. It should not be called directly by
    business code.

    Args:
        db: Database session
        from_qiao_id: Sender's qiao_id (use "system" for system messages)
        to_qiao_id: Receiver's qiao_id
        conv_id: Conversation ID (empty string for NOTIFICATION)
        content: Message content
        message_type: Message type

    Returns:
        MessageResult from provider
    """
    provider = get_default_provider(db)
    encrypted_content, encryption_meta = encrypt_for_transport(content)
    merged_extra_fields = dict(extra_fields or {})
    merged_extra_fields.update(encryption_meta)

    if from_qiao_id == "system":
        result = await provider.send_message_as_system(
            to_qiao_id=to_qiao_id,
            conv_id=conv_id,
            content=encrypted_content,
            message_type=message_type,
            action=action,
            extra_fields=merged_extra_fields,
            msg_id=msg_id,
        )
    else:
        result = await provider.send_message(
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            conv_id=conv_id,
            content=encrypted_content,
            message_type=message_type,
            extra_fields=merged_extra_fields,
        )

    return result, encryption_meta


async def send_message(
    db: AsyncSession,
    *,
    from_qiao_id: str,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int = MessageType.TEXT,
    action: Optional[dict] = None,
    extra_fields: Optional[dict] = None,
    msg_id: Optional[str] = None,
) -> None:
    """
    Send message (stored in message_history).

    Supports message types: TEXT, TYPING_START, TYPING_END, CHAT_INFO

    Args:
        db: Database session
        from_qiao_id: Sender's qiao_id (use "system" for CHAT_INFO)
        to_qiao_id: Receiver's qiao_id
        conv_id: Internal conversation ID
        content: Message content
        message_type: Message type (default: TEXT)

    Raises:
        ValueError: If message sending fails
    """
    sent_at_ms = int(time.time() * 1000)
    msg_id_server = f"msg_{generate_snowflake_id()}"

    # Send through provider (handles encryption)
    result, encryption_meta = await _send_message_internal(
        db=db,
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
        conv_id=conv_id,
        content=content,
        message_type=message_type,
        action=action,
        extra_fields=extra_fields,
        msg_id=msg_id,
    )

    if not result.success:
        logger.error(
            "message_send_failed",
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            error=result.error_message,
        )
        raise ValueError(f"Failed to send message: {result.error_message}")

    # Store to message_history
    metadata = EventMetadata(
        action=action,
        notification_type=(extra_fields or {}).get("notification_type") if extra_fields else None,
        encryption=encryption_meta.get("encryption"),
        encryption_version=encryption_meta.get("enc_version"),
    )
    provider_metadata = ProviderMetadata()

    # Update event with provider message ID after successful send
    outbound_event = OutboundMessageEvent(
        message_type=MessageType(message_type),
        conversation_id=conv_id,
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
        content=content,
        sent_at_ms=sent_at_ms,
        msg_id_server=msg_id_server,
        msg_id_provider_outbound=result.msg_id_provider,
        supports_typing=True,
        metadata=metadata,
        provider_metadata=provider_metadata,
    )

    # Store to message_history using unified event object
    await store_message_to_db(db, outbound_event)

    logger.info(
        "message_sent",
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
        conv_id=conv_id,
        msg_id_provider=result.msg_id_provider,
    )


async def send_notification(
    db: AsyncSession,
    *,
    to_qiao_id: str,
    notification_type: int,
    action_data: dict,
) -> None:
    """
    Send notification (stored in notification_push_history).

    Args:
        db: Database session
        to_qiao_id: Receiver's qiao_id
        notification_type: Notification type (from NotificationType enum)
        action_data: Notification action data containing:
            - action: {type, target}
            - data: notification-specific data
    """
    # Create notification record
    notification = await notification_crud.create_notification(
        db,
        to_qiao_id=to_qiao_id,
        notification_type=notification_type,
        action_data=action_data,
    )

    logger.info(
        "notification_record_created",
        notification_id=notification.id,
        to_qiao_id=to_qiao_id,
        notification_type=notification_type,
    )

    # Build payload metadata for transport
    notification_payload = {
        "notification_type": notification_type,
        "data": action_data.get("data", {}),
    }
    fallback_content = action_data.get("data", {}).get("message", "")

    # Send through internal function
    result, encryption_meta = await _send_message_internal(
        db=db,
        from_qiao_id="system",
        to_qiao_id=to_qiao_id,
        conv_id="",  # Notification messages don't have conv_id
        content=fallback_content,
        message_type=MessageType.NOTIFICATION,
        action=action_data.get("action"),
        extra_fields=notification_payload,
    )

    if not result.success:
        # Mark notification as failed
        await notification_crud.mark_as_failed(
            db,
            notification_id=notification.id,
            error_message=result.error_message or "Unknown error",
        )

        logger.error(
            "notification_send_failed",
            notification_id=notification.id,
            to_qiao_id=to_qiao_id,
            error=result.error_message,
        )
        # Non-critical, don't raise
        return

    logger.info(
        "notification_sent",
        notification_id=notification.id,
        to_qiao_id=to_qiao_id,
        notification_type=notification_type,
    )
