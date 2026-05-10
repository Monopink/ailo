"""
Message storage service.

Unified service for storing all types of messages to message_history table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ContactType,
    MessageDirection,
    MessageParticipantType,
    MessageType,
)
from app.models.contact import Contact
from app.models.message.message import MessageHistory
from app.services.message.schemas import InboundMessageEvent, OutboundMessageEvent
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)

# Constants for timestamp conversion
# Threshold to distinguish between seconds and milliseconds timestamps
# Any timestamp > 1e11 (Nov 1973 in seconds, ~1970 in milliseconds) is treated as milliseconds
TIMESTAMP_MILLISECOND_THRESHOLD = 1e11


async def store_message(
    db: AsyncSession,
    event: InboundMessageEvent | OutboundMessageEvent,
    *,
    contact: Contact,
) -> MessageHistory | None:
    """
    Store message to message_history from event object.

    This is the primary interface following the unified event schema
    (docs/spec/message/schema.md).

    Args:
        db: Database session
        event: InboundMessageEvent or OutboundMessageEvent
        contact: Contact record bound to the conversation_id

    Returns:
        Created MessageHistory object

    Raises:
        ValueError: If participant not found
    """
    if event.message_type in (MessageType.TYPING_START, MessageType.TYPING_END):
        return None

    # Determine direction based on event type
    if isinstance(event, InboundMessageEvent):
        direction = MessageDirection.INBOUND
    elif isinstance(event, OutboundMessageEvent):
        direction = MessageDirection.OUTBOUND
    else:
        raise TypeError(f"Unsupported event type: {type(event)}")

    # Extract metadata dict from EventMetadata model
    metadata_dict = event.metadata.model_dump(exclude_none=True) if event.metadata else {}

    from_type, from_id = _resolve_participant_from_contact(contact, event.from_qiao_id)
    to_type, to_id = _resolve_participant_from_contact(contact, event.to_qiao_id)

    # Call internal implementation
    return await _store_message_internal(
        db=db,
        conv_id=event.conversation_id,
        from_qiao_id=event.from_qiao_id,
        to_qiao_id=event.to_qiao_id,
        from_type=from_type,
        from_id=from_id,
        to_type=to_type,
        to_id=to_id,
        content=event.content,
        message_type=event.message_type,
        direction=direction,
        msg_id_provider_inbound=event.msg_id_provider_inbound
        if isinstance(event, InboundMessageEvent)
        else None,
        msg_id_client=event.msg_id_client,
        client_sent_at=event.client_sent_time_ms,
        sent_at=event.sent_at_ms,
        msg_id_server=event.msg_id_server,
        metadata=metadata_dict,
        inbound_provider=event.inbound_provider if isinstance(event, InboundMessageEvent) else None,
        inbound_device_id=event.inbound_device_id
        if isinstance(event, InboundMessageEvent)
        else None,
        llm_request_id=event.llm_request_id if isinstance(event, OutboundMessageEvent) else None,
    )


async def _store_message_internal(
    db: AsyncSession,
    *,
    conv_id: str,
    from_qiao_id: str,
    to_qiao_id: str,
    from_type: MessageParticipantType,
    from_id: int,
    to_type: MessageParticipantType,
    to_id: int,
    content: str,
    message_type: int,
    direction: int,
    msg_id_provider_inbound: str | None = None,
    msg_id_client: str | None = None,
    client_sent_at: int | float | str | datetime | None = None,
    sent_at: int | float | str | datetime | None = None,
    msg_id_server: str | None = None,
    metadata: dict[str, Any] | None = None,
    inbound_provider: int | None = None,
    inbound_device_id: str | None = None,
    llm_request_id: int | None = None,
) -> MessageHistory:
    """
    Store message to message_history.

    Unified storage service for all message types (user, AI, system).

    Args:
        db: Database session
        conv_id: Internal conversation ID
        from_qiao_id: Sender's qiao_id (use "system" for system messages)
        to_qiao_id: Receiver's qiao_id
        content: Message content
        message_type: Message type
        direction: Message direction (1=INBOUND, 2=OUTBOUND)
        from_type: Sender participant type
        from_id: Sender internal ID
        to_type: Receiver participant type
        to_id: Receiver internal ID
        msg_id_provider_inbound: Inbound provider message ID (optional)
        msg_id_client: Client message ID (optional, for user messages)
        client_sent_time: Client sent timestamp in ms epoch or datetime
            (optional, for user messages)
        sent_at: Server-side event timestamp (ms epoch/datetime).
            Defaults to client_sent_time or now.
        msg_id_server: Optional pre-generated msg_id_server (otherwise auto-generated)
        metadata: Message metadata (optional)

    Returns:
        Created MessageHistory object

    Raises:
        ValueError: If participant not found
    """
    msg_id_server_value = msg_id_server or f"msg_{generate_snowflake_id()}"

    # Normalize optional client timestamp (epoch milliseconds in client payloads)
    normalized_client_sent_time = _normalize_client_sent_time(client_sent_at)
    normalized_sent_at = _normalize_client_sent_time(sent_at)
    if normalized_sent_at is None:
        normalized_sent_at = normalized_client_sent_time or datetime.now(UTC)

    normalized_inbound_device_id: UUID | None = None
    if inbound_device_id:
        try:
            normalized_inbound_device_id = UUID(inbound_device_id)
        except ValueError:
            logger.warning("invalid_inbound_device_id", value=inbound_device_id)
            normalized_inbound_device_id = None

    # Create message record
    message_data = {
        "id": generate_snowflake_id(),
        "msg_id_provider_inbound": msg_id_provider_inbound,
        "msg_id_client": msg_id_client,
        "msg_id_server": msg_id_server_value,
        "conversation_id": conv_id,
        "direction": direction,
        "from_type": from_type,
        "from_id": from_id,
        "from_qiao_id": from_qiao_id,
        "to_type": to_type,
        "to_id": to_id,
        "to_qiao_id": to_qiao_id,
        "message_type": message_type,
        "content": content,
        "inbound_provider": inbound_provider,
        "inbound_device_id": normalized_inbound_device_id,
        "llm_request_id": llm_request_id,
        "client_sent_at": normalized_client_sent_time,
        "sent_at": normalized_sent_at,
        "message_metadata": metadata or {},
    }

    message_obj = MessageHistory(**message_data)
    db.add(message_obj)
    await db.flush()

    logger.debug(
        "message_stored",
        msg_id_server=msg_id_server_value,
        conv_id=conv_id,
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
        message_type=message_type,
        direction=direction,
    )

    return message_obj


def _normalize_client_sent_time(
    client_sent_time: int | float | str | datetime | None,
) -> datetime | None:
    """Convert heterogeneous client timestamps to timezone-aware datetime."""
    if client_sent_time is None:
        return None

    if isinstance(client_sent_time, datetime):
        return client_sent_time if client_sent_time.tzinfo else client_sent_time.replace(tzinfo=UTC)

    if isinstance(client_sent_time, int | float):
        # Treat large values as milliseconds, otherwise assume seconds.
        seconds = (
            client_sent_time / 1000
            if client_sent_time > TIMESTAMP_MILLISECOND_THRESHOLD
            else client_sent_time
        )
        return datetime.fromtimestamp(seconds, tz=UTC)

    if isinstance(client_sent_time, str):
        try:
            parsed = datetime.fromisoformat(client_sent_time.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            logger.warning(
                "invalid_client_sent_time_format",
                value=client_sent_time,
            )
            return None

    # Fallback for unsupported types (defensive programming)
    logger.warning(  # type: ignore[unreachable]
        "unsupported_client_sent_time_type",
        provided_type=type(client_sent_time).__name__,
    )
    return None


def _resolve_participant_from_contact(
    contact: Contact, qiao_id: str
) -> tuple[MessageParticipantType, int]:
    """Resolve participant type and ID using the bound contact record."""
    if qiao_id == "system":
        return MessageParticipantType.SYSTEM, 0

    if qiao_id == contact.user_qiao_id:
        if contact.user_id is None:
            logger.error("contact_user_id_missing", conversation_id=contact.conversation_id)
            raise ValueError("Contact user_id missing for message participant resolution.")
        return MessageParticipantType.USER, contact.user_id

    if qiao_id == contact.contact_qiao_id:
        if contact.contact_type == ContactType.AI:
            participant_type = MessageParticipantType.AI
        else:
            participant_type = MessageParticipantType.USER
        return participant_type, contact.contact_id

    logger.error(
        "participant_qiao_id_mismatch",
        conversation_id=contact.conversation_id,
        qiao_id=qiao_id,
        user_qiao_id=contact.user_qiao_id,
        contact_qiao_id=contact.contact_qiao_id,
    )
    raise ValueError("Participant qiao_id does not match contact record.")
