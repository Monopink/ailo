"""
Inbound message parser (business layer).

Converts intermediate format to InboundMessageEvent with business logic.
"""

from app.enums import MessageType
from app.services.message.schemas import EventMetadata, InboundMessageEvent, ProviderMetadata
from app.services.message.security.encryption import decrypt_from_transport
from app.type_defs import JSONDict
from app.utils.logging import get_logger

logger = get_logger(__name__)


def parse_to_event(intermediate: JSONDict) -> InboundMessageEvent | None:
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
            raise TypeError("missing_required_fields")

        # Type guards: ensure all required fields are correct types
        if not isinstance(from_qiao_id_raw, str) or not from_qiao_id_raw:
            logger.error("invalid_from_qiao_id_type", value=from_qiao_id_raw)
            raise TypeError("invalid_from_qiao_id_type")

        if not isinstance(to_qiao_id_raw, str) or not to_qiao_id_raw:
            logger.error("invalid_to_qiao_id_type", value=to_qiao_id_raw)
            raise TypeError("invalid_to_qiao_id_type")

        if not isinstance(conv_id_raw, str) or not conv_id_raw:
            logger.error("invalid_conversation_id_type", value=conv_id_raw)
            raise TypeError("invalid_conversation_id_type")

        if not isinstance(message_type_raw, int):
            logger.error(
                "invalid_message_type",
                message_type=message_type_raw,
                expected_type="int",
            )
            raise TypeError("invalid_message_type")

        # Type narrowing complete - assign to typed variables
        from_qiao_id: str = from_qiao_id_raw
        to_qiao_id: str = to_qiao_id_raw
        conv_id: str = conv_id_raw

        # Decrypt content if encrypted
        content_raw = intermediate.get("content", "")

        # Validate content type
        if not isinstance(content_raw, str):
            logger.error("invalid_content_type", content_type=type(content_raw).__name__)
            raise TypeError("invalid_content_type")

        content: str = content_raw
        action_value = intermediate.get("action")
        action = action_value if isinstance(action_value, dict) else None

        notification_type_value = intermediate.get("notification_type")
        notification_type = (
            int(notification_type_value)
            if isinstance(notification_type_value, (int, float))
            else None
        )

        encryption_algo_value = intermediate.get("encryption")
        encryption_algo = encryption_algo_value if isinstance(encryption_algo_value, str) else None
        encryption_version_value = intermediate.get("encryption_version")
        encryption_version = (
            encryption_version_value if isinstance(encryption_version_value, str) else None
        )
        supports_typing_raw = intermediate.get("supports_typing", False)
        supports_typing = (
            bool(supports_typing_raw)
            if isinstance(supports_typing_raw, (bool, int, float))
            else False
        )
        client_sent_time_value = intermediate.get("sent_time")
        client_sent_time = (
            int(client_sent_time_value)
            if isinstance(client_sent_time_value, (int, float))
            else None
        )

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
            action=action,
            notification_type=notification_type,
            encryption=encryption_algo,
            encryption_version=encryption_version,
        )

        lc_from_value = intermediate.get("lc_from")
        lc_from = lc_from_value if isinstance(lc_from_value, str) else None

        lc_conv_id_value = intermediate.get("lc_conv_id")
        lc_conv_id = lc_conv_id_value if isinstance(lc_conv_id_value, str) else None

        raw_webhook_value = intermediate.get("raw_webhook")
        raw_webhook = raw_webhook_value if isinstance(raw_webhook_value, str) else None

        notification_data_value = intermediate.get("notification_data")
        notification_data = (
            notification_data_value if isinstance(notification_data_value, dict) else None
        )

        # Build provider metadata
        provider_metadata = ProviderMetadata(
            lc_from=lc_from,
            lc_conv_id=lc_conv_id,
            raw_webhook=raw_webhook,
            notification_data=notification_data,
        )

        # Validate timestamp_ms type
        timestamp_ms_raw = intermediate.get("timestamp_ms")
        if not isinstance(timestamp_ms_raw, int):
            logger.error("invalid_timestamp_type", timestamp_type=type(timestamp_ms_raw).__name__)
            raise TypeError("invalid_timestamp_type")

        timestamp_ms: int = timestamp_ms_raw

        # Validate msg_id_client type (required for InboundMessageEvent)
        msg_id_client_raw = intermediate.get("msg_id_client")
        if not isinstance(msg_id_client_raw, str) or not msg_id_client_raw:
            logger.error("invalid_msg_id_client_type", value=msg_id_client_raw)
            raise TypeError("invalid_msg_id_client_type")

        msg_id_client: str = msg_id_client_raw

        # Validate msg_id_provider type (required for InboundMessageEvent)
        msg_id_provider_raw = intermediate.get("msg_id_provider")
        if not isinstance(msg_id_provider_raw, str) or not msg_id_provider_raw:
            logger.error("invalid_msg_id_provider_type", value=msg_id_provider_raw)
            raise TypeError("invalid_msg_id_provider_type")

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
            supports_typing=supports_typing,
            client_sent_time=client_sent_time,
            metadata=event_metadata,
            provider_metadata=provider_metadata,
        )

    except Exception as e:
        logger.error("parse_to_event_error", error=str(e), exc_info=True)
        return None
