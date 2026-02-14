"""
LeanCloud message format adapter.

Handles LeanCloud-specific format conversion without business logic.
"""

import json
import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.system import system_configs
from app.enums import MessageTransportProvider
from app.type_defs import JSONDict, JSONValue
from app.utils.logging import get_logger

logger = get_logger(__name__)

BUSINESS_MESSAGE_TYPE = 1


async def parse_webhook_to_dict(db: AsyncSession, webhook_payload: JSONDict) -> JSONDict | None:
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
        created_at_entry = webhook_payload.get("createdAt")
        created_at_iso = (
            created_at_entry.get("iso")
            if isinstance(created_at_entry, dict) and isinstance(created_at_entry.get("iso"), str)
            else None
        )

        conv_entry = webhook_payload.get("conv")
        lc_conv_id = (
            conv_entry.get("objectId")
            if isinstance(conv_entry, dict) and isinstance(conv_entry.get("objectId"), str)
            else None
        )

        if not all([msg_id_provider, data_str, created_at_iso, lc_conv_id]):
            logger.error(
                "lc_missing_required_fields",
                has_msgId=bool(msg_id_provider),
                has_data=bool(data_str),
                has_createdAt=bool(created_at_iso),
                has_conv=bool(lc_conv_id),
            )
            raise ValueError("missing_required_fields")

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
            raise ValueError("wrong_conversation")

        # Parse inner message JSON (TypedMessage format or flattened JSON)
        if isinstance(data_str, dict | list):
            inner_message = data_str
        else:
            # Type guard: validate data_str before json.loads
            if data_str is None or not isinstance(data_str, str | bytes):
                logger.error(
                    "invalid_data_str_type",
                    data_str_type=type(data_str).__name__ if data_str is not None else "None",
                )
                raise ValueError("invalid_data_str_type")

            try:
                inner_message = json.loads(data_str)
            except json.JSONDecodeError as e:
                logger.error("lc_invalid_json", data=data_str, error=str(e))
                raise ValueError("lc_invalid_json")

        if not isinstance(inner_message, dict):
            logger.error("lc_invalid_message_payload", payload=inner_message)
            raise TypeError("invalid_message_payload")

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
            raise ValueError("unsupported_message_type")

        attrs = inner_message.get("_lcattrs")
        if not isinstance(attrs, dict):
            attrs = {}
        outer_fields = {
            "from": lc_from,
            "to": webhook_payload.get("to"),
        }

        def _extract(
            field: str,
            *sources: JSONDict,
            default: JSONValue | None = None,
        ) -> JSONValue | None:
            """Extract field from first source dict that contains it."""
            for source in sources:
                if field in source and source[field] is not None:
                    return source[field]
            return default

        msg_id_client = _extract("msg_id", attrs, inner_message)
        from_qiao_id = _extract("from_qiao_id", attrs, inner_message, outer_fields, default=lc_from)
        to_qiao_id = _extract("to_qiao_id", attrs, inner_message, outer_fields)
        conversation_id = _extract("conversation_id", attrs, inner_message)
        content = _extract("content", attrs, inner_message, default="") or ""
        message_type = _extract("message_type", attrs, inner_message)
        supports_typing_raw = _extract("supports_typing", attrs, inner_message, default=False)
        supports_typing = (
            bool(supports_typing_raw)
            if isinstance(supports_typing_raw, bool | int | float)
            else False
        )
        sent_time_raw = _extract("sent_time", attrs, inner_message)
        sent_time = int(sent_time_raw) if isinstance(sent_time_raw, int | float) else None
        action_raw = _extract("action", attrs, inner_message)
        action = action_raw if isinstance(action_raw, dict) else None
        notification_type_raw = _extract("notification_type", attrs, inner_message)
        notification_type = (
            int(notification_type_raw) if isinstance(notification_type_raw, int | float) else None
        )
        notification_data_raw = _extract("data", attrs, inner_message)
        notification_data = (
            notification_data_raw if isinstance(notification_data_raw, dict) else None
        )
        encryption_raw = _extract("encryption", attrs, inner_message)
        encryption = encryption_raw if isinstance(encryption_raw, str) else None
        encryption_version_raw = _extract("enc_version", attrs, inner_message)
        encryption_version = (
            encryption_version_raw if isinstance(encryption_version_raw, str) else None
        )

        # Convert ISO timestamp to milliseconds
        timestamp_ms: int
        if isinstance(created_at_iso, str):
            try:
                dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
                timestamp_ms = int(dt.timestamp() * 1000)
            except (ValueError, AttributeError) as e:
                logger.error("lc_invalid_timestamp", iso=created_at_iso, error=str(e))
                timestamp_ms = sent_time or int(datetime.now(tz=UTC).timestamp() * 1000)
        else:
            timestamp_ms = sent_time or int(datetime.now(tz=UTC).timestamp() * 1000)

        # Return intermediate format (business layer will process further)
        return {
            "inbound_provider": MessageTransportProvider.LEANCLOUD,
            "inbound_device_id": None,
            "msg_id_provider": msg_id_provider,
            "msg_id_client": msg_id_client,
            "from_qiao_id": from_qiao_id,
            "to_qiao_id": to_qiao_id,
            "conversation_id": conversation_id,
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
        }

    except Exception as e:
        logger.error("lc_adapter_error", error=str(e), exc_info=True)
        return None


def build_outbound_typed_message(
    *,
    from_qiao_id: str,
    to_qiao_id: str,
    conversation_id: str,
    content: str,
    message_type: int,
    msg_id: str,
    supports_typing: bool = True,
    action: JSONDict | None = None,
    extra_fields: JSONDict | None = None,
) -> str:
    """
    Build LeanCloud message payload from business layer data.

    Provider layer responsibility: Construct LeanCloud-specific JSON format.

    Args:
        from_qiao_id: Sender qiao_id
        to_qiao_id: Receiver qiao_id
        conversation_id: Internal conversation identifier
        content: Message content (already encrypted by business layer)
        message_type: Message type
        msg_id: Optional message ID
        action: Optional action dict
        extra_fields: Optional extra fields (encryption metadata, etc)

    Returns:
        JSON string for LeanCloud API
    """
    if not isinstance(msg_id, str) or not msg_id:
        logger.error(
            "lc_outbound_msg_id_missing",
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            conversation_id=conversation_id,
            message_type=message_type,
        )
        raise ValueError("msg_id is required for outbound messages.")

    attrs: dict[str, JSONValue] = {
        "msg_id": msg_id,
        "from_qiao_id": from_qiao_id,
        "to_qiao_id": to_qiao_id,
        "conversation_id": conversation_id,
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
