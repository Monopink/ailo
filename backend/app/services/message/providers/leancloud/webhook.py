"""
LeanCloud message provider webhook handler.

This module provides webhook handling for LeanCloud messaging service,
parsing incoming messages and converting them to standardized format.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from crud.contact import contact as contact_crud
from enums import MessageType
from services.message.schemas import EventMetadata, InboundMessageEvent, ProviderMetadata
from services.message.security.encryption import decrypt_from_transport
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logging import get_logger

from .adapter import parse_webhook_to_dict

logger = get_logger(__name__)


async def parse_leancloud_webhook(
    db: AsyncSession, message: Dict[str, Any]
) -> Optional[InboundMessageEvent]:
    """
    Parse incoming webhook data from LeanCloud.

    LeanCloud webhook format:
    {
      "msgId": "nYH9iBSBS_uogCEgvZwE7Q",
      "from": "qiao_user001",
      "data": "{\"from\":\"qiao_user001\",\"to\":\"qiao_xm001\",\"conv_id\":\"conv_xyz789\",\"content\":\"你好\",\"message_type\":1}",
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
            return None

        from_qiao_id = intermediate.get("from_qiao_id")
        to_qiao_id = intermediate.get("to_qiao_id")
        conv_id = intermediate.get("conv_id")
        content = intermediate.get("content") or ""
        message_type = intermediate.get("message_type")
        supports_typing = intermediate.get("supports_typing", False)
        sent_time = intermediate.get("sent_time")
        action = intermediate.get("action")
        notification_type = intermediate.get("notification_type")
        notification_data = intermediate.get("notification_data")
        encryption_algo = intermediate.get("encryption")
        encryption_version = intermediate.get("encryption_version")

        if not all([from_qiao_id, to_qiao_id, conv_id, message_type is not None]):
            logger.error(
                "missing_inner_message_fields",
                has_from=bool(from_qiao_id),
                has_to=bool(to_qiao_id),
                has_conv_id=bool(conv_id),
                has_message_type=message_type is not None,
                intermediate=intermediate,
            )
            return None

        # Verify conversation exists in contacts table
        contact = await contact_crud.get_by_conv_id(db, conv_id=conv_id)
        if not contact:
            logger.warning("conversation_not_found", conv_id=conv_id)
            return None

        # Convert ISO timestamp to milliseconds
        timestamp = intermediate.get("timestamp_ms")
        if not timestamp:
            timestamp = sent_time if sent_time else int(datetime.now().timestamp() * 1000)

        # Build metadata and apply decryption if needed
        encryption_metadata = {}
        if encryption_algo:
            encryption_metadata = {
                "encryption": encryption_algo,
                "enc_version": encryption_version,
            }
            try:
                content = decrypt_from_transport(content, encryption_metadata)
            except ValueError as e:
                logger.error(
                    "leancloud_decrypt_failed",
                    error=str(e),
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
        provider_metadata = ProviderMetadata(
            lc_from=intermediate.get("lc_from"),
            lc_conv_id=intermediate.get("lc_conv_id"),
            raw_webhook=intermediate.get("raw_webhook"),
            notification_data=notification_data,
        )

        # 9. Return InboundMessageEvent (msg_id_server to be filled downstream)
        return InboundMessageEvent(
            message_type=MessageType(message_type),
            conversation_id=conv_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            content=content or "",
            sent_at_ms=timestamp,
            msg_id_client=intermediate.get("msg_id_client"),
            msg_id_provider_inbound=intermediate.get("msg_id_provider"),
            supports_typing=supports_typing,
            client_sent_time=sent_time,
            metadata=event_metadata,
            provider_metadata=provider_metadata,
        )

    except Exception as e:
        logger.error("webhook_parse_error", error=str(e), error_type=type(e).__name__, message=message)
        return None
