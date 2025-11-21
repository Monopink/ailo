"""
LeanCloud message format adapter.

Handles LeanCloud-specific format conversion without business logic.
"""

import json
from datetime import datetime
import time
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from crud.system import system_configs
from utils.logging import get_logger

logger = get_logger(__name__)

BUSINESS_MESSAGE_TYPE = 1


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

        # Parse inner message JSON (TypedMessage format or flattened JSON)
        if isinstance(data_str, (dict, list)):
            inner_message = data_str
        else:
            try:
                inner_message = json.loads(data_str)
            except json.JSONDecodeError as e:
                logger.error("lc_invalid_json", data=data_str, error=str(e))
                return None

        if not isinstance(inner_message, dict):
            logger.error("lc_invalid_message_payload", payload=inner_message)
            return None

        logger.info(
            "lc_incoming_message",
            lctype=inner_message.get("_lctype"),
            has_lcattrs=isinstance(inner_message.get("_lcattrs"), dict),
            inner=inner_message,
        )

        if inner_message.get("_lctype") != BUSINESS_MESSAGE_TYPE:
            logger.warning(
                "lc_unsupported_message_type",
                lctype=inner_message.get("_lctype"),
                expected=BUSINESS_MESSAGE_TYPE,
            )
            return None

        attrs = inner_message.get("_lcattrs")
        if not isinstance(attrs, dict):
            attrs = {}
        outer_fields = {
            "from": lc_from,
            "to": webhook_payload.get("to"),
        }

        def _extract(field: str, *sources: Dict[str, Any], default: Any = None) -> Any:
            for source in sources:
                if not isinstance(source, dict):
                    continue
                if field in source and source[field] is not None:
                    return source[field]
            return default

        msg_id_client = _extract("msg_id", attrs, inner_message)
        from_qiao_id = _extract("from_qiao_id", attrs, inner_message, outer_fields, default=lc_from)
        to_qiao_id = _extract("to_qiao_id", attrs, inner_message, outer_fields)
        conv_id = _extract("conv_id", attrs, inner_message)
        content = _extract("content", attrs, inner_message, default="") or ""
        message_type = _extract("message_type", attrs, inner_message)
        supports_typing = bool(_extract("supports_typing", attrs, inner_message, default=False))
        sent_time = _extract("sent_time", attrs, inner_message)
        action = _extract("action", attrs, inner_message)
        notification_type = _extract("notification_type", attrs, inner_message)
        notification_data = _extract("data", attrs, inner_message)
        encryption = _extract("encryption", attrs, inner_message)
        encryption_version = _extract("enc_version", attrs, inner_message)

        # Convert ISO timestamp to milliseconds
        try:
            dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
            timestamp_ms = int(dt.timestamp() * 1000)
        except (ValueError, AttributeError) as e:
            logger.error("lc_invalid_timestamp", iso=created_at_iso, error=str(e))
            timestamp_ms = sent_time or int(datetime.now().timestamp() * 1000)

        # Return intermediate format (business layer will process further)
        return {
            "msg_id_provider": msg_id_provider,
            "msg_id_client": msg_id_client,
            "from_qiao_id": from_qiao_id,
            "to_qiao_id": to_qiao_id,
            "conv_id": conv_id,
            "content": content,
            "message_type": message_type,
            "supports_typing": supports_typing,
            "sent_time": sent_time,
            "timestamp_ms": timestamp_ms,
            "action": action,
            "notification_type": notification_type,
            "notification_data": notification_data,
            "encryption": encryption,
            "encryption_version": encryption_version,
            # Provider metadata
            "lc_from": lc_from,
            "lc_conv_id": lc_conv_id,
            "raw_webhook": json.dumps(webhook_payload, ensure_ascii=False),
        }

    except Exception as e:
        logger.error("lc_adapter_error", error=str(e), exc_info=True)
        return None


def build_outbound_typed_message(
    *,
    from_qiao_id: str,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int,
    msg_id: str,
    supports_typing: bool = True,
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
    attrs: Dict[str, Any] = {
        "msg_id": msg_id,
        "from_qiao_id": from_qiao_id,
        "to_qiao_id": to_qiao_id,
        "conv_id": conv_id,
        "content": content,
        "message_type": message_type,
        "supports_typing": supports_typing,
        "sent_time": int(time.time() * 1000),
    }

    if action:
        attrs["action"] = action

    if extra_fields:
        attrs.update(extra_fields)

    payload = {
        "_lctype": BUSINESS_MESSAGE_TYPE,
        "_lcattrs": attrs,
    }

    return json.dumps(payload, ensure_ascii=False)
