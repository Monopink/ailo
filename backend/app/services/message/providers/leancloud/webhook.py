"""
LeanCloud message provider webhook handler.

This module provides webhook handling for LeanCloud messaging service,
parsing incoming messages and converting them to standardized format.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from enums import MessageType
from services.message.schemas import EventMetadata, InboundMessageEvent, ProviderMetadata
from services.message.security.encryption import decrypt_from_transport
from crud.system import system_configs
from crud.contact import contact as contact_crud
from utils.logging import get_logger

logger = get_logger(__name__)


async def parse_leancloud_webhook(db: AsyncSession, message: Dict[str, Any]) -> Optional[InboundMessageEvent]:
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
        # 1. Extract LeanCloud outer fields
        msg_id_provider = message.get("msgId")
        lc_from = message.get("from")
        data_str = message.get("data")
        created_at_iso = message.get("createdAt", {}).get("iso")
        lc_conv_id = message.get("conv", {}).get("objectId")

        if not all([msg_id_provider, data_str, created_at_iso, lc_conv_id]):
            logger.error(
                "missing_required_fields",
                has_msgId=bool(msg_id_provider),
                has_data=bool(data_str),
                has_createdAt=bool(created_at_iso),
                has_conv=bool(lc_conv_id),
            )
            return None

        # 2. Verify LeanCloud IM conversation ID matches system conversation
        system_conv_id = await system_configs.get_config_value(db, config_key="leancloud_im_service_conversation_id")

        if lc_conv_id != system_conv_id:
            logger.warning(
                "message_not_from_system_conversation",
                lc_conv_id=lc_conv_id,
                system_conv_id=system_conv_id,
            )
            return None

        # 3. Parse inner message format (JSON string in data field)
        try:
            inner_message = json.loads(data_str)
        except json.JSONDecodeError as e:
            logger.error("invalid_message_data_json", data=data_str, error=str(e))
            return None

        # 4. Extract inner message fields
        msg_id = inner_message.get("msg_id")
        from_qiao_id = inner_message.get("from")
        to_qiao_id = inner_message.get("to")
        conv_id = inner_message.get("conv_id")
        content = inner_message.get("content") or ""
        message_type = inner_message.get("message_type")
        supports_typing = inner_message.get("supports_typing", False)
        sent_time = inner_message.get("sent_time")
        action = inner_message.get("action")
        notification_type = inner_message.get("notification_type")
        notification_data = inner_message.get("data")
        follow_up_hint = inner_message.get("follow_up_hint")
        encryption_algo = inner_message.get("encryption")
        encryption_version = inner_message.get("enc_version")

        # Validate required fields
        if not all([from_qiao_id, to_qiao_id, conv_id, message_type is not None]):
            logger.error(
                "missing_inner_message_fields",
                has_from=bool(from_qiao_id),
                has_to=bool(to_qiao_id),
                has_conv_id=bool(conv_id),
                has_message_type=message_type is not None,
            )
            return None

        # 5. Verify conversation exists in contacts table
        contact = await contact_crud.get_by_conv_id(db, conv_id=conv_id)
        if not contact:
            logger.warning("conversation_not_found", conv_id=conv_id)
            return None

        # 6. Convert ISO timestamp to milliseconds
        try:
            dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
            timestamp = int(dt.timestamp() * 1000)
        except (ValueError, AttributeError) as e:
            logger.error("invalid_timestamp_format", iso=created_at_iso, error=str(e))
            # Use sent_time as fallback
            timestamp = sent_time if sent_time else int(datetime.now().timestamp() * 1000)

        # 7. Build metadata and apply decryption if needed
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
                    msg_id=msg_id,
                )

        # 8. Build event metadata payloads
        event_metadata = EventMetadata(
            action=action,
            notification_type=notification_type,
            follow_up_hint=follow_up_hint,
            rate_limit_bucket=None,
            encryption=encryption_algo,
            encryption_version=encryption_version,
        )
        provider_metadata = ProviderMetadata(
            lc_from=lc_from,
            lc_conv_id=lc_conv_id,
            raw_webhook=json.dumps(message, ensure_ascii=False),
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
            msg_id_client=msg_id,
            msg_id_provider_inbound=msg_id_provider,
            supports_typing=supports_typing,
            client_sent_time=sent_time,
            metadata=event_metadata,
            provider_metadata=provider_metadata,
        )

    except Exception as e:
        logger.error("webhook_parse_error", error=str(e), error_type=type(e).__name__, message=message)
        return None
