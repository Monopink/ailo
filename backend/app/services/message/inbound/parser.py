"""
Inbound message parser (business layer).

Converts intermediate format to InboundMessageEvent with business logic.
"""

from typing import Any, Dict, Optional

from enums import MessageType
from services.message.schemas import EventMetadata, InboundMessageEvent, ProviderMetadata
from services.message.security.encryption import decrypt_from_transport
from utils.logging import get_logger

logger = get_logger(__name__)


def parse_to_event(intermediate: Dict[str, Any]) -> Optional[InboundMessageEvent]:
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
        from_qiao_id = intermediate.get("from_qiao_id")
        to_qiao_id = intermediate.get("to_qiao_id")
        conv_id = intermediate.get("conv_id")
        message_type = intermediate.get("message_type")

        if not all([from_qiao_id, to_qiao_id, conv_id, message_type is not None]):
            logger.error(
                "missing_required_fields",
                has_from=bool(from_qiao_id),
                has_to=bool(to_qiao_id),
                has_conv_id=bool(conv_id),
                has_message_type=message_type is not None,
            )
            return None

        # Decrypt content if encrypted
        content = intermediate.get("content", "")
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

        # Build InboundMessageEvent
        return InboundMessageEvent(
            message_type=MessageType(message_type),
            conversation_id=conv_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            content=content,
            sent_at_ms=intermediate.get("timestamp_ms"),
            msg_id_client=intermediate.get("msg_id_client"),
            msg_id_provider_inbound=intermediate.get("msg_id_provider"),
            supports_typing=intermediate.get("supports_typing", False),
            client_sent_time=intermediate.get("sent_time"),
            metadata=event_metadata,
            provider_metadata=provider_metadata,
        )

    except Exception as e:
        logger.error("parse_to_event_error", error=str(e), exc_info=True)
        return None
