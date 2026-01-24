"""
LeanCloud message provider webhook handler.

This module provides webhook handling for LeanCloud messaging service,
parsing incoming messages and converting them to standardized format.
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.contact import contact as contact_crud
from app.enums import MessageType
from app.services.message.schemas import EventMetadata, InboundMessageEvent
from app.services.message.security.encryption import decrypt_from_transport
from app.type_defs import JSONDict
from app.utils.logging import get_logger

from .adapter import parse_webhook_to_dict

logger = get_logger(__name__)


async def parse_leancloud_webhook(
    db: AsyncSession, message: JSONDict
) -> InboundMessageEvent | None:
    """
    Parse incoming webhook data from LeanCloud.

    LeanCloud webhook format:
    {
      "msgId": "nYH9iBSBS_uogCEgvZwE7Q",
      "from": "qiao_user001",
      "data": "{\"from\":\"qiao_user001\",\"to\":\"qiao_xm001\",...}",
      "conv": {"objectId": "68edda0a554ecc6e8843b246"},
      "createdAt": {"iso": "2015-07-30T14:37:42.584Z"}
    }

    Inner message format (in data field):
    {
      "msg_id": "client_1710001111222_abc123",
      "from": "qiao_user001",
      "to": "qiao_xm001",
      "conv_id": "conv_xyz789",
      "content": "你好",
      "message_type": 1,
      "supports_typing": true,
      "sent_time": 1710001111222
    }

    Args:
        db: Database session
        message: Raw webhook payload from LeanCloud

    Returns:
        InboundMessageEvent if valid, None if invalid/should be ignored
    """
    try:
        intermediate = await parse_webhook_to_dict(db, message)
        if not intermediate:
            raise TypeError("empty_intermediate_payload")

        from_qiao_id = intermediate.get("from_qiao_id")
        to_qiao_id = intermediate.get("to_qiao_id")
        conv_id = intermediate.get("conv_id")
        content_value = intermediate.get("content")
        content = content_value if isinstance(content_value, str) else ""
        message_type_raw = intermediate.get("message_type")
        supports_typing_raw = intermediate.get("supports_typing", False)
        supports_typing = (
            bool(supports_typing_raw)
            if isinstance(supports_typing_raw, bool | int | float)
            else False
        )
        sent_time_raw = intermediate.get("sent_time")
        sent_time = int(sent_time_raw) if isinstance(sent_time_raw, int | float) else None
        action_raw = intermediate.get("action")
        action = action_raw if isinstance(action_raw, dict) else None
        notification_type_raw = intermediate.get("notification_type")
        notification_type = (
            int(notification_type_raw) if isinstance(notification_type_raw, int | float) else None
        )
        encryption_raw = intermediate.get("encryption")
        encryption_algo = encryption_raw if isinstance(encryption_raw, str) else None
        encryption_version_raw = intermediate.get("encryption_version")
        encryption_version = (
            encryption_version_raw if isinstance(encryption_version_raw, str) else None
        )

        if not all([from_qiao_id, to_qiao_id, conv_id, message_type_raw is not None]):
            logger.error(
                "missing_inner_message_fields",
                has_from=bool(from_qiao_id),
                has_to=bool(to_qiao_id),
                has_conv_id=bool(conv_id),
                has_message_type=message_type_raw is not None,
                intermediate=intermediate,
            )
            raise TypeError("missing_required_inner_fields")

        # Type narrowing - ensure required string fields are strings
        if not isinstance(from_qiao_id, str):
            logger.error("invalid_from_qiao_id_type", type=type(from_qiao_id).__name__)
            raise TypeError("invalid_from_qiao_id_type")
        if not isinstance(to_qiao_id, str):
            logger.error("invalid_to_qiao_id_type", type=type(to_qiao_id).__name__)
            raise TypeError("invalid_to_qiao_id_type")
        if not isinstance(conv_id, str):
            logger.error("invalid_conv_id_type", type=type(conv_id).__name__)
            raise TypeError("invalid_conv_id_type")

        # Type narrowing - validate message_type is int
        if not isinstance(message_type_raw, int):
            logger.error(
                "invalid_message_type",
                message_type=message_type_raw,
                expected_type="int",
            )
            raise TypeError("invalid_message_type")

        # Verify conversation exists in contacts table
        contact = await contact_crud.get_by_conv_id(db, conv_id=conv_id)
        if not contact:
            logger.warning("conversation_not_found", conv_id=conv_id)
            raise TypeError("conversation_not_found")

        # Convert ISO timestamp to milliseconds
        timestamp_raw = intermediate.get("timestamp_ms")
        timestamp = int(timestamp_raw) if isinstance(timestamp_raw, int | float) else None
        if not timestamp:
            timestamp = sent_time if sent_time else int(datetime.now(UTC).timestamp() * 1000)

        # Build metadata and apply decryption if needed
        encryption_metadata = {}
        if encryption_algo:
            encryption_metadata = {
                "encryption": encryption_algo,
                "enc_version": encryption_version,
            }
            try:
                content = decrypt_from_transport(content, encryption_metadata)
            except ValueError:
                logger.exception(
                    "leancloud_decrypt_failed",
                    msg_id=intermediate.get("msg_id_client"),
                )

        # Build event metadata payloads
        event_metadata = EventMetadata(
            action=action,
            notification_type=notification_type,
            rate_limit_bucket=None,
            encryption=encryption_algo,
            encryption_version=encryption_version,
        )

        # Extract and validate required message IDs
        msg_id_client = intermediate.get("msg_id_client")
        msg_id_provider = intermediate.get("msg_id_provider")

        if not isinstance(msg_id_client, str):
            logger.error("invalid_msg_id_client_type", type=type(msg_id_client).__name__)
            raise TypeError("invalid_msg_id_client_type")
        if not isinstance(msg_id_provider, str):
            logger.error("invalid_msg_id_provider_type", type=type(msg_id_provider).__name__)
            raise TypeError("invalid_msg_id_provider_type")

        # 9. Return InboundMessageEvent (msg_id_server to be filled downstream)
        return InboundMessageEvent(
            message_type=MessageType(message_type_raw),
            conversation_id=conv_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            content=content or "",
            sent_at_ms=timestamp,
            msg_id_client=msg_id_client,
            msg_id_provider_inbound=msg_id_provider,
            supports_typing=supports_typing,
            client_sent_time=sent_time,
            metadata=event_metadata,
        )

    except Exception:
        logger.exception(
            "webhook_parse_error",
            message=message,
        )
        return None
