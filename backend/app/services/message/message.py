import random
from typing import Optional, Union, Dict, Any
from datetime import datetime

from core.database import SessionLocal
from core.event_bus import event_bus, EventTypes
from crud.message import message_crud
from enums import (
    MessageType,
    MessageTypeCategory,
    SystemMessageStatus,
    SystemMessageReason,
    SystemMessageAction,
)
from utils.logging import get_logger

logger = get_logger(__name__)

# Initialize module
logger.info("message_module_initialized")


def _validate_message(message: dict) -> bool:
    """
    Validate message format

    Args:
        message: Message dictionary to validate

    Returns:
        bool: True if message is valid, False otherwise
    """
    required_fields = [
        "from_entity",
        "to_entity",
        "message_service",
    ]

    # For content messages, message_type is required
    if "content" not in message:
        required_fields.append("message_type")

    if not all(field in message for field in required_fields):
        logger.warning("message_missing_fields", message=message)
        return False
    return True


def generate_message_id() -> str:
    """
    Generate unique message ID

    Returns:
        str: Unique message ID in format msg_{timestamp}_{random_string}
    """
    timestamp = int(datetime.now().timestamp() * 1000)  # milliseconds
    # Use same character set as entity_id generation for consistency
    chars = "23456789abcdefghjkmnpqrstuvwxyz"
    random_part = "".join(random.choices(chars, k=8))
    return f"msg_{timestamp}_{random_part}"


async def save_message(message: dict, message_status: str = "sent") -> None:
    """
    Save message to database
    Only filters out STATUS category messages (typing indicators), saves all others

    Args:
        message: Message dictionary to save
        message_status: Message status, defaults to "sent"
    """
    try:
        message_type_value = message.get("message_type")
        if not message_type_value:
            logger.warning("missing_message_type", message=message)
            return

        message_type = MessageType.parse(message_type_value)

        # Skip only STATUS category messages (typing indicators)
        if message_type and message_type.category == MessageTypeCategory.STATUS:
            logger.info(
                "skipping_status_message_save",
                message_type=message_type.name,
                from_entity=message.get("from_entity"),
            )
            return

        # Save all other messages (CONTENT and SYSTEM)
        # Add status field and convert message_type to name for database storage
        message_with_status = message.copy()
        message_with_status["status"] = message_status
        # Convert numeric message_type to name for consistent database storage
        if message_type:
            message_with_status["message_type"] = message_type.name

        async with SessionLocal() as db:
            await message_crud.save_message(db, message_with_status)
        logger.info(
            "message_saved",
            message_type=message_type.name if message_type else "unknown",
            from_entity=message.get("from_entity"),
            status=message_status,
        )
    except Exception as e:
        logger.error("message_save_error", error=str(e), exc_info=True)


async def send_message(
    from_entity: str,
    to_entity: str,
    message_type: str,
    message_service: str,
    content: Optional[Union[str, Dict[str, Any]]] = None,
    message_id: Optional[str] = None,
    **kwargs,
) -> None:
    """
    Send message with explicit parameters

    Args:
        from_entity: Sender entity ID
        to_entity: Receiver entity ID
        message_type: Message type code (string)
        message_service: Service type
        content: Message content (string for chat, dict for system)
        message_id: Optional message ID
        **kwargs: Additional fields for extensibility
    """
    try:
        # Convert to internal message dict for processing
        message = {
            "from_entity": from_entity,
            "to_entity": to_entity,
            "message_type": message_type,
            "message_service": message_service,
            "content": content,
            "message_id": message_id,
            **kwargs,
        }

        # Parse message type
        if not message_type:
            logger.error("missing_message_type", message=message)
            return

        message_type_obj = MessageType.parse(message_type)
        if not message_type_obj:
            logger.error("invalid_message_type", message_type_value=message_type)
            return

        # Validate message format
        if not _validate_message(message):
            logger.error("invalid_message", message=message)
            return

        # Generate unique message ID if not present (for all outgoing messages)
        if not message.get("message_id"):
            message["message_id"] = generate_message_id()
            logger.debug("message_id_generated", message_id=message["message_id"])

        # Future extension point: message processing hooks
        # This is where message signing, encryption, or other processing could be added
        # await _process_message_hooks(message, message_type_obj)

        # Publish to event bus for delivery
        await event_bus.publish(EventTypes.SEND_MESSAGE, message)

        # Save messages to database based on category
        # CONTENT and SYSTEM messages are saved, STATUS messages are not
        if message_type_obj.category != MessageTypeCategory.STATUS:
            await save_message(message)

        logger.info(
            "message_sent",
            message_id=message.get("message_id"),
            from_entity=from_entity,
            to_entity=to_entity,
            message_type=message_type_obj.name,
            category=message_type_obj.category,
        )

    except Exception as e:
        logger.error("message_processing_error", error=str(e), exc_info=True)


async def send_system_message(
    from_entity: str,
    to_entity: str,
    action: SystemMessageAction,
    target_message_id: Optional[str] = None,
    status: Optional[SystemMessageStatus] = None,
    reason: Optional[SystemMessageReason] = None,
    contact_id: Optional[str] = None,
    custom_message: Optional[str] = None,
) -> None:
    """
    Send system message with proper content structure

    Args:
        from_entity: Source entity ID (for chat window identification)
        to_entity: Target entity ID
        action: System message action type
        target_message_id: Client-side message ID that this system message refers to (for MESSAGE_STATUS)
        status: System message status (for MESSAGE_STATUS)
        reason: Failure reason code (for MESSAGE_STATUS)
        contact_id: Contact entity ID (for NEW_CONTACT)
        custom_message: Optional custom message text
    """
    try:
        # Build content based on action type
        content: Dict[str, Any] = {"action": action.value}

        if action == SystemMessageAction.MESSAGE_STATUS:
            if target_message_id and status and reason:
                content.update(
                    {
                        "target_message_id": target_message_id,
                        "status": status.value,
                        "reason": reason.value,
                    }
                )
            else:
                logger.error(
                    "missing_message_status_fields",
                    target_message_id=target_message_id,
                    status=status,
                    reason=reason,
                )
                return

        elif action == SystemMessageAction.NEW_CONTACT:
            if contact_id:
                content.update({"contact_id": contact_id})
            else:
                logger.error("missing_contact_id_for_new_contact", contact_id=contact_id)
                return

        # Add custom message to content if provided
        if custom_message:
            content["message"] = custom_message

        # Send system message using the unified send_message function
        await send_message(
            from_entity=from_entity,
            to_entity=to_entity,
            message_type=str(MessageType.SYSTEM.code),
            message_service="system",
            content=content,
        )

        logger.info(
            "system_message_sent",
            from_entity=from_entity,
            to_entity=to_entity,
            action=action.name,
            content=content,
        )

    except Exception as e:
        logger.error("system_message_send_error", error=str(e), exc_info=True)


async def receive_message(message: dict) -> None:
    """
    Unified message receiving processing function (RECEIVED_MESSAGE event handler)

    Args:
        message: Message dictionary from external sources (LeanCloud, WebSocket)
    """
    try:
        # Validate message format
        if not _validate_message(message):
            logger.error("invalid_received_message", message=message)
            return

        # Save received message to database (preserves external_msg_id, status="sent")
        await save_message(message, message_status="sent")

        # Import here to avoid circular dependency
        from services.ai_chat.model_router import model_router

        # Route message to AI model processing
        await model_router.route_message(message)

        logger.info(
            "received_message_processed",
            from_entity=message.get("from_entity"),
            to_entity=message.get("to_entity"),
            message_type=message.get("message_type"),
        )

    except Exception as e:
        logger.error("received_message_processing_error", error=str(e), exc_info=True)


# Subscribe to RECEIVED_MESSAGE events when module is imported
event_bus.subscribe(EventTypes.RECEIVED_MESSAGE, receive_message)
logger.info("message_module_subscribed_to_received_message_events")
