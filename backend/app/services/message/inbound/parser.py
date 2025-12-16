"""
Inbound message parser (business layer).

Converts intermediate format to InboundMessageEvent with business logic.
"""

from typing import Any

from app.enums import MessageType
from app.services.message.schemas import EventMetadata, InboundMessageEvent, ProviderMetadata
from app.services.message.security.encryption import decrypt_from_transport
from app.utils.logging import get_logger

logger = get_logger(__name__)


def parse_to_event(intermediate: dict[str, Any]) -> InboundMessageEvent | None:
    """
    Parse intermediate format to InboundMessageEvent.

    Business layer responsibility:
    - Decrypt content
    - Validate required fields
    - Build InboundMessageEvent

    Args:
        intermediate: Intermediate dict from provider adapter

    Returns:
        InboundMessageEvent or None if invalid
    """
    try:
        # Validate required fields
        from_qiao_id_raw = intermediate.get("from_qiao_id")
        to_qiao_id_raw = intermediate.get("to_qiao_id")
        conv_id_raw = intermediate.get("conv_id")
        message_type_raw = intermediate.get("message_type")

        if not all([from_qiao_id_raw, to_qiao_id_raw, conv_id_raw, message_type_raw is not None]):
            logger.error(
                "missing_required_fields",
                has_from=bool(from_qiao_id_raw),
                has_to=bool(to_qiao_id_raw),
                has_conv_id=bool(conv_id_raw),
                has_message_type=message_type_raw is not None,
            )
            return None

        # Type guards: ensure all required fields are correct types
        if not isinstance(from_qiao_id_raw, str) or not from_qiao_id_raw:
            logger.error("invalid_from_qiao_id_type", value=from_qiao_id_raw)
            return None

        if not isinstance(to_qiao_id_raw, str) or not to_qiao_id_raw:
            logger.error("invalid_to_qiao_id_type", value=to_qiao_id_raw)
            return None

        if not isinstance(conv_id_raw, str) or not conv_id_raw:
            logger.error("invalid_conversation_id_type", value=conv_id_raw)
            return None

        if not isinstance(message_type_raw, int):
            logger.error(
                "invalid_message_type",
                message_type=message_type_raw,
                expected_type="int",
            )
            return None

        # Type narrowing complete - assign to typed variables
        from_qiao_id: str = from_qiao_id_raw
        to_qiao_id: str = to_qiao_id_raw
        conv_id: str = conv_id_raw

        # Decrypt content if encrypted
        content_raw = intermediate.get("content", "")

        # Validate content type
        if not isinstance(content_raw, str):
            logger.error("invalid_content_type", content_type=type(content_raw).__name__)
            return None

        content: str = content_raw
        encryption_algo = intermediate.get("encryption")
        encryption_version = intermediate.get("encryption_version")

        if encryption_algo:
            encryption_metadata = {
                "encryption": encryption_algo,
                "enc_version": encryption_version,
            }
            try:
                content = decrypt_from_transport(content, encryption_metadata)
            except ValueError as e:
                logger.error(
                    "decrypt_failed",
                    error=str(e),
                    msg_id=intermediate.get("msg_id_client"),
                )

        # Build event metadata
        event_metadata = EventMetadata(
            action=intermediate.get("action"),
            notification_type=intermediate.get("notification_type"),
            encryption=encryption_algo,
            encryption_version=encryption_version,
        )

        # Build provider metadata
        provider_metadata = ProviderMetadata(
            lc_from=intermediate.get("lc_from"),
            lc_conv_id=intermediate.get("lc_conv_id"),
            raw_webhook=intermediate.get("raw_webhook"),
        )

        # Validate timestamp_ms type
        timestamp_ms_raw = intermediate.get("timestamp_ms")
        if not isinstance(timestamp_ms_raw, int):
            logger.error("invalid_timestamp_type", timestamp_type=type(timestamp_ms_raw).__name__)
            return None

        timestamp_ms: int = timestamp_ms_raw

        # Validate msg_id_client type (required for InboundMessageEvent)
        msg_id_client_raw = intermediate.get("msg_id_client")
        if not isinstance(msg_id_client_raw, str) or not msg_id_client_raw:
            logger.error("invalid_msg_id_client_type", value=msg_id_client_raw)
            return None

        msg_id_client: str = msg_id_client_raw

        # Validate msg_id_provider type (required for InboundMessageEvent)
        msg_id_provider_raw = intermediate.get("msg_id_provider")
        if not isinstance(msg_id_provider_raw, str) or not msg_id_provider_raw:
            logger.error("invalid_msg_id_provider_type", value=msg_id_provider_raw)
            return None

        msg_id_provider: str = msg_id_provider_raw

        # Build InboundMessageEvent
        return InboundMessageEvent(
            message_type=MessageType(message_type_raw),
            conversation_id=conv_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            content=content,
            sent_at_ms=timestamp_ms,
            msg_id_client=msg_id_client,
            msg_id_provider_inbound=msg_id_provider,
            supports_typing=intermediate.get("supports_typing", False),
            client_sent_time=intermediate.get("sent_time"),
            metadata=event_metadata,
            provider_metadata=provider_metadata,
        )

    except Exception as e:
        logger.error("parse_to_event_error", error=str(e), exc_info=True)
        return None
