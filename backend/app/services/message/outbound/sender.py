"""Message sending service (business layer)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.contact import contact as contact_crud
from app.crud.message import notification_push_history as notification_crud
from app.enums import MessageType
from app.schemas.message import NotificationActionData
from app.services.message.dispatch.outbox import enqueue_timeline_fanout
from app.services.message.dispatch.realtime import fanout_typing_event
from app.services.message.providers.factory import get_default_provider
from app.services.message.schemas import EventMetadata, OutboundMessageEvent
from app.services.message.security.encryption import encrypt_for_transport
from app.services.message.storage.persistence import store_message as store_message_to_db
from app.type_defs import JSONDict, JSONValue
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

if TYPE_CHECKING:
    from app.services.message.providers.base import MessageResult

logger = get_logger(__name__)

_TIMELINE_MESSAGE_TYPES = {MessageType.TEXT, MessageType.CHAT_INFO}


def _extract_notification_type(extra_fields: JSONDict | None) -> int | None:
    if extra_fields is None:
        return None
    value = extra_fields.get("notification_type")
    return value if isinstance(value, int) else None


def _build_event_metadata(
    *,
    action: JSONDict | None,
    extra_fields: JSONDict | None,
) -> EventMetadata:
    return EventMetadata(
        action=action,
        notification_type=_extract_notification_type(extra_fields),
    )


async def _send_message_internal(
    db: AsyncSession,
    *,
    from_qiao_id: str,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int,
    sent_at_ms: int,
    action: JSONDict | None = None,
    extra_fields: JSONDict | None = None,
    msg_id: str | None = None,
) -> tuple[MessageResult, JSONDict]:
    """Send immediately via default provider (used for non-timeline events)."""
    if not isinstance(msg_id, str) or not msg_id:
        raise ValueError("msg_id is required for outbound provider send.")

    provider = get_default_provider(db)
    encrypted_content, encryption_meta = encrypt_for_transport(content)
    merged_extra_fields = dict(extra_fields or {})
    merged_extra_fields.update(encryption_meta)
    merged_extra_fields["sent_time"] = sent_at_ms

    if from_qiao_id == "system":
        result = await provider.send_message_as_system(
            to_qiao_id=to_qiao_id,
            conv_id=conv_id,
            content=encrypted_content,
            message_type=message_type,
            action=action,
            extra_fields=merged_extra_fields,
            msg_id=msg_id,
        )
    else:
        result = await provider.send_message(
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            conv_id=conv_id,
            content=encrypted_content,
            message_type=message_type,
            extra_fields=merged_extra_fields,
            msg_id=msg_id,
        )

    return result, encryption_meta


async def fanout_realtime_typing_best_effort(
    db: AsyncSession,
    *,
    from_qiao_id: str,
    to_qiao_id: str,
    conv_id: str,
    typing_state: str,
    sent_at_ms: int | None = None,
) -> None:
    """Best-effort typing fanout that never blocks timeline sending."""
    if not conv_id:
        logger.error("typing_dispatch_skipped_missing_conv_id")
        return

    if typing_state not in {"start", "end"}:
        logger.error("typing_dispatch_skipped_invalid_state", typing_state=typing_state)
        return

    contact = await contact_crud.get_by_conversation_id(db, conversation_id=conv_id)
    if not contact:
        logger.error("contact_not_found_for_realtime_typing", conversation_id=conv_id)
        return
    if not isinstance(contact.user_id, int):
        logger.error("contact_user_id_missing_for_realtime_typing", conversation_id=conv_id)
        return

    effective_time_ms = sent_at_ms if sent_at_ms is not None else int(time.time() * 1000)
    try:
        await fanout_typing_event(
            db,
            owner_user_id=contact.user_id,
            conversation_id=conv_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            typing_state=typing_state,
            time_ms=effective_time_ms,
        )
    except Exception:
        logger.exception(
            "typing_dispatch_failed_unexpected",
            conversation_id=conv_id,
            from_qiao_id=from_qiao_id,
            to_qiao_id=to_qiao_id,
            typing_state=typing_state,
        )


async def send_timeline_message(
    db: AsyncSession,
    *,
    from_qiao_id: str,
    to_qiao_id: str,
    conv_id: str,
    content: str,
    message_type: int = MessageType.TEXT,
    action: JSONDict | None = None,
    extra_fields: JSONDict | None = None,
    msg_id: str | None = None,
    llm_request_id: int | None = None,
) -> str:
    """Persist one timeline message and enqueue outbox dispatch."""
    normalized_message_type = MessageType(int(message_type))

    if normalized_message_type not in _TIMELINE_MESSAGE_TYPES:
        raise ValueError(f"Unsupported outbound message_type={normalized_message_type}")
    if not conv_id:
        raise ValueError("conv_id is required for timeline message persistence.")

    contact = await contact_crud.get_by_conversation_id(db, conversation_id=conv_id)
    if not contact:
        logger.error("contact_not_found_for_outbound", conversation_id=conv_id)
        raise ValueError("Contact not found for outbound message persistence.")
    if not isinstance(contact.user_id, int):
        logger.error("contact_user_id_missing_for_outbound", conversation_id=conv_id)
        raise TypeError("Contact user_id missing for outbound dispatch owner.")

    sent_at_ms = int(time.time() * 1000)
    outbound_event = OutboundMessageEvent(
        message_type=normalized_message_type,
        conversation_id=conv_id,
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
        content=content,
        sent_at_ms=sent_at_ms,
        msg_id_server=msg_id or f"msg_{generate_snowflake_id()}",
        supports_typing=True,
        metadata=_build_event_metadata(action=action, extra_fields=extra_fields),
        llm_request_id=llm_request_id,
    )

    stored = await store_message_to_db(db, outbound_event, contact=contact)
    if stored is None:
        raise ValueError("Timeline outbound message was not persisted.")

    await enqueue_timeline_fanout(
        db,
        msg_id_server=stored.msg_id_server,
        owner_user_id=contact.user_id,
    )

    logger.info(
        "timeline_message_enqueued",
        conversation_id=conv_id,
        msg_id_server=stored.msg_id_server,
        from_qiao_id=from_qiao_id,
        to_qiao_id=to_qiao_id,
    )
    return stored.msg_id_server


async def send_notification(
    db: AsyncSession,
    *,
    to_qiao_id: str,
    notification_type: int,
    action_data: NotificationActionData,
) -> None:
    """Send notification (not part of timeline outbox dispatch)."""
    notification = await notification_crud.create_notification(
        db,
        to_qiao_id=to_qiao_id,
        notification_type=notification_type,
        action_data=action_data.model_dump(mode="json"),
    )

    logger.info(
        "notification_record_created",
        notification_id=notification.id,
        to_qiao_id=to_qiao_id,
        notification_type=notification_type,
    )

    msg_id_server = f"msg_{generate_snowflake_id()}"
    sent_at_ms = int(time.time() * 1000)

    notification_payload: dict[str, JSONValue] = {
        "notification_type": notification_type,
        "data": action_data.data.model_dump(mode="json"),
    }
    fallback_content = action_data.data.message

    result, _ = await _send_message_internal(
        db=db,
        from_qiao_id="system",
        to_qiao_id=to_qiao_id,
        conv_id="",
        content=fallback_content,
        message_type=MessageType.NOTIFICATION,
        sent_at_ms=sent_at_ms,
        action=action_data.action.model_dump(mode="json"),
        extra_fields=notification_payload,
        msg_id=msg_id_server,
    )

    if not result.success:
        await notification_crud.mark_as_failed(
            db,
            notification_id=notification.id,
            error_message=result.error_message or "Unknown error",
        )
        logger.error(
            "notification_send_failed",
            notification_id=notification.id,
            to_qiao_id=to_qiao_id,
            error=result.error_message,
        )
        return

    logger.info(
        "notification_sent",
        notification_id=notification.id,
        to_qiao_id=to_qiao_id,
        notification_type=notification_type,
        msg_id=msg_id_server,
    )
