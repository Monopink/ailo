"""
Message storage service.

Unified service for storing all types of messages to message_history table.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from enums import MessageDirection, MessageParticipantType, MessageStatus, ServiceProvider
from models.message.message import MessageHistory
from services.message.schemas import InboundMessageEvent, OutboundMessageEvent
from services.message.storage.participant_resolver import get_participant_info
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger
from utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)


async def store_message(
    db: AsyncSession,
    event: Union[InboundMessageEvent, OutboundMessageEvent],
) -> MessageHistory:
    """
    Store message to message_history from event object.

    This is the primary interface following the unified event schema
    (docs/development/message-events-schema.md).

    Args:
        db: Database session
        event: InboundMessageEvent or OutboundMessageEvent

    Returns:
        Created MessageHistory object

    Raises:
        ValueError: If participant not found
    """
    # Determine direction and provider ID based on event type
    if isinstance(event, InboundMessageEvent):
        direction = MessageDirection.INBOUND
        msg_id_provider = event.msg_id_provider_inbound
    elif isinstance(event, OutboundMessageEvent):
        direction = MessageDirection.OUTBOUND
        msg_id_provider = event.msg_id_provider_outbound
    else:
        raise ValueError(f"Unsupported event type: {type(event)}")

    # Extract metadata dict from EventMetadata model
    metadata_dict = event.metadata.model_dump(exclude_none=True) if event.metadata else {}

    # Call internal implementation
    return await _store_message_internal(
        db=db,
        conv_id=event.conversation_id,
        from_qiao_id=event.from_qiao_id,
        to_qiao_id=event.to_qiao_id,
        content=event.content,
        message_type=event.message_type,
        direction=direction,
        msg_id_provider=msg_id_provider,
        msg_id_client=event.msg_id_client,
        client_sent_time=event.client_sent_time,
        sent_at=event.sent_at_ms,
        msg_id_server=event.msg_id_server,
        metadata=metadata_dict,
    )


async def _store_message_internal(
    db: AsyncSession,
    *,
    conv_id: str,
    from_qiao_id: str,
    to_qiao_id: str,
    content: str,
    message_type: int,
    direction: int,
    msg_id_provider: Optional[str] = None,
    msg_id_client: Optional[str] = None,
    client_sent_time: Optional[Union[int, float, str, datetime]] = None,
    sent_at: Optional[Union[int, float, str, datetime]] = None,
    msg_id_server: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
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
        msg_id_provider: Provider message ID (optional)
        msg_id_client: Client message ID (optional, for user messages)
        client_sent_time: Client sent timestamp in ms epoch or datetime (optional, for user messages)
        sent_at: Server-side event timestamp (ms epoch/datetime). Defaults to client_sent_time or now.
        msg_id_server: Optional pre-generated msg_id_server (otherwise auto-generated)
        metadata: Message metadata (optional)

    Returns:
        Created MessageHistory object

    Raises:
        ValueError: If participant not found
    """
    msg_id_server_value = msg_id_server or f"msg_{generate_snowflake_id()}"
    # Get participant types and IDs
    from_type, from_id = await _get_participant_info(db, from_qiao_id)
    to_type, to_id = await _get_participant_info(db, to_qiao_id)

    # Determine service provider
    service_provider = ServiceProvider.LEANCLOUD if msg_id_provider else ServiceProvider.INTERNAL

    # Normalize optional client timestamp (LeanCloud sends epoch milliseconds)
    normalized_client_sent_time = _normalize_client_sent_time(client_sent_time)
    normalized_sent_at = _normalize_client_sent_time(sent_at)
    if normalized_sent_at is None:
        normalized_sent_at = normalized_client_sent_time or datetime.now(timezone.utc)

    # Create message record
    message_data = {
        "id": generate_snowflake_id(),
        "msg_id_provider_inbound": msg_id_provider if direction == 1 else None,
        "msg_id_provider_outbound": msg_id_provider if direction == 2 else None,
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
        "service_provider": service_provider,
        "status": MessageStatus.SENT,
        "client_sent_time": normalized_client_sent_time,
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
    client_sent_time: Optional[Union[int, float, str, datetime]],
) -> Optional[datetime]:
    """Convert heterogeneous client timestamps to timezone-aware datetime."""
    if client_sent_time is None:
        return None

    if isinstance(client_sent_time, datetime):
        return (
            client_sent_time if client_sent_time.tzinfo else client_sent_time.replace(tzinfo=timezone.utc)
        )

    if isinstance(client_sent_time, (int, float)):
        # Treat large values as milliseconds, otherwise assume seconds.
        seconds = client_sent_time / 1000 if client_sent_time > 1e11 else client_sent_time
        return datetime.fromtimestamp(seconds, tz=timezone.utc)

    if isinstance(client_sent_time, str):
        try:
            parsed = datetime.fromisoformat(client_sent_time.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning(
                "invalid_client_sent_time_format",
                value=client_sent_time,
            )
            return None

    logger.warning(
        "unsupported_client_sent_time_type",
        provided_type=type(client_sent_time).__name__,
    )
    return None


async def _get_participant_info(db: AsyncSession, qiao_id: str) -> tuple[MessageParticipantType, int]:
    """Get participant info (delegates to participant_resolver)."""
    return await get_participant_info(db, qiao_id)
