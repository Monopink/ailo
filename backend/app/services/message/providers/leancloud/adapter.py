"""
LeanCloud message format adapter.

Handles LeanCloud-specific format conversion without business logic.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from crud.system import system_configs
from utils.logging import get_logger

logger = get_logger(__name__)


async def parse_webhook_to_dict(
    db: AsyncSession, webhook_payload: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Parse LeanCloud webhook payload to intermediate dict format.

    Provider layer responsibility: Extract and validate LeanCloud-specific fields only.
    Does NOT perform business logic (decryption, contact validation, etc).

    Args:
        db: Database session (for LeanCloud config verification)
        webhook_payload: Raw LeanCloud webhook payload

    Returns:
        Intermediate dict with extracted fields, or None if invalid
    """
    try:
        # Extract LeanCloud outer fields
        msg_id_provider = webhook_payload.get("msgId")
        lc_from = webhook_payload.get("from")
        data_str = webhook_payload.get("data")
        created_at_iso = webhook_payload.get("createdAt", {}).get("iso")
        lc_conv_id = webhook_payload.get("conv", {}).get("objectId")

        if not all([msg_id_provider, data_str, created_at_iso, lc_conv_id]):
            logger.error(
                "lc_missing_required_fields",
                has_msgId=bool(msg_id_provider),
                has_data=bool(data_str),
                has_createdAt=bool(created_at_iso),
                has_conv=bool(lc_conv_id),
            )
            return None

        # Verify LeanCloud conversation ID matches system conversation
        system_conv_id = await system_configs.get_config_value(
            db, config_key="leancloud_im_service_conversation_id"
        )

        if lc_conv_id != system_conv_id:
            logger.warning(
                "lc_wrong_conversation",
                lc_conv_id=lc_conv_id,
                system_conv_id=system_conv_id,
            )
            return None

        # Parse inner message JSON
        try:
            inner_message = json.loads(data_str)
        except json.JSONDecodeError as e:
            logger.error("lc_invalid_json", data=data_str, error=str(e))
            return None

        # Convert ISO timestamp to milliseconds
        try:
            dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
            timestamp_ms = int(dt.timestamp() * 1000)
        except (ValueError, AttributeError) as e:
            logger.error("lc_invalid_timestamp", iso=created_at_iso, error=str(e))
            timestamp_ms = inner_message.get("sent_time") or int(datetime.now().timestamp() * 1000)

        # Return intermediate format (business layer will process further)
        return {
            "msg_id_provider": msg_id_provider,
            "msg_id_client": inner_message.get("msg_id"),
            "from_qiao_id": inner_message.get("from"),
            "to_qiao_id": inner_message.get("to"),
            "conv_id": inner_message.get("conv_id"),
            "content": inner_message.get("content") or "",
            "message_type": inner_message.get("message_type"),
            "supports_typing": inner_message.get("supports_typing", False),
            "sent_time": inner_message.get("sent_time"),
            "timestamp_ms": timestamp_ms,
            "action": inner_message.get("action"),
            "notification_type": inner_message.get("notification_type"),
            "notification_data": inner_message.get("data"),
            "follow_up_hint": inner_message.get("follow_up_hint"),
            "encryption": inner_message.get("encryption"),
            "encryption_version": inner_message.get("enc_version"),
            # Provider metadata
            "lc_from": lc_from,
            "lc_conv_id": lc_conv_id,
            "raw_webhook": json.dumps(webhook_payload, ensure_ascii=False),
        }

    except Exception as e:
        logger.error("lc_adapter_error", error=str(e), exc_info=True)
        return None


def build_outbound_payload(
    from_qiao_id: str,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int,
    msg_id: Optional[str] = None,
    action: Optional[dict] = None,
    extra_fields: Optional[dict] = None,
) -> str:
    """
    Build LeanCloud message payload from business layer data.

    Provider layer responsibility: Construct LeanCloud-specific JSON format.

    Args:
        from_qiao_id: Sender qiao_id
        to_qiao_id: Receiver qiao_id
        conv_id: Internal conversation ID
        content: Message content (already encrypted by business layer)
        message_type: Message type
        msg_id: Optional message ID
        action: Optional action dict
        extra_fields: Optional extra fields (encryption metadata, etc)

    Returns:
        JSON string for LeanCloud API
    """
    import time

    payload = {
        "from": from_qiao_id,
        "to": to_qiao_id,
        "conv_id": conv_id,
        "content": content,
        "message_type": message_type,
        "sent_time": int(time.time() * 1000),
    }

    if msg_id:
        payload["msg_id"] = msg_id

    if action:
        payload["action"] = action

    if extra_fields:
        payload.update(extra_fields)

    return json.dumps(payload, ensure_ascii=False)
