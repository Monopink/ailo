"""Message sending service (business layer)."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.contact import contact as contact_crud
from app.crud.message import notification_push_history as notification_crud
from app.crud.user import user as user_crud
from app.enums import MessageDeliveryStatus, MessageTransportProvider, MessageType
from app.models.message import MessageEndpoint
from app.schemas.message import NotificationActionData
from app.services.message.dispatch.delivery_records import upsert_delivery
from app.services.message.dispatch.outbox import enqueue_timeline_fanout
from app.services.message.dispatch.realtime import fanout_typing_event
from app.services.message.schemas import EventMetadata, OutboundMessageEvent
from app.services.message.security.encryption import encrypt_for_transport
from app.services.message.storage.persistence import store_message as store_message_to_db
from app.services.message.websocket.manager import ws_manager
from app.type_defs import JSONDict, JSONValue
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)

_TIMELINE_MESSAGE_TYPES = {MessageType.TEXT, MessageType.CHAT_INFO}


def _now_utc() -> datetime:
    return datetime.now(UTC)


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
    """Send notification event through websocket delivery command chain."""

    msg_id_server = f"msg_{generate_snowflake_id()}"
    sent_at_ms = int(time.time() * 1000)
    content, _ = encrypt_for_transport(action_data.data.message)
    notification_message: dict[str, JSONValue] = {
        "msg_id_server": msg_id_server,
        "msg_id_client": None,
        "conversation_id": "",
        "from_qiao_id": "system",
        "to_qiao_id": to_qiao_id,
        "content": content,
        "message_type": int(MessageType.NOTIFICATION),
        "client_sent_time_ms": None,
        "sent_time_ms": sent_at_ms,
        "metadata": {
            "action": action_data.action.model_dump(mode="json"),
            "notification_type": notification_type,
            "data": action_data.data.model_dump(mode="json"),
        },
    }

    owner_user = await user_crud.get_by_qiao_id(db, qiao_id=to_qiao_id)
    owner_user_id = int(owner_user.id) if owner_user is not None else None

    if owner_user_id is None:
        notification = await notification_crud.create_notification(
            db,
            to_qiao_id=to_qiao_id,
            notification_type=notification_type,
            action_data=action_data.model_dump(mode="json"),
            msg_id_server=msg_id_server,
            planned_endpoint_count=0,
        )
        await notification_crud.mark_as_failed(
            db,
            notification_id=notification.id,
            error_message="Recipient user not found",
        )
        logger.error("notification_send_failed_user_not_found", to_qiao_id=to_qiao_id)
        return

    now = _now_utc()
    endpoints_result = await db.execute(
        select(MessageEndpoint).where(
            and_(
                MessageEndpoint.user_id == owner_user_id,
                MessageEndpoint.provider == MessageTransportProvider.WEBSOCKET,
                or_(
                    MessageEndpoint.lease_expires_at.is_(None),
                    MessageEndpoint.lease_expires_at > now,
                ),
            )
        )
    )
    endpoints = list(endpoints_result.scalars().all())

    notification = await notification_crud.create_notification(
        db,
        to_qiao_id=to_qiao_id,
        notification_type=notification_type,
        action_data=action_data.model_dump(mode="json"),
        msg_id_server=msg_id_server,
        planned_endpoint_count=len(endpoints),
    )

    logger.info(
        "notification_record_created",
        notification_id=notification.id,
        to_qiao_id=to_qiao_id,
        notification_type=notification_type,
        planned_endpoint_count=len(endpoints),
    )

    if not endpoints:
        await notification_crud.mark_as_failed(
            db,
            notification_id=notification.id,
            error_message="No active websocket endpoint",
        )
        logger.error(
            "notification_send_failed",
            notification_id=notification.id,
            to_qiao_id=to_qiao_id,
            error="No active websocket endpoint",
        )
        return

    frame_base = {
        "type": "event",
        "payload": {
            "event_type": "message",
            "message": notification_message,
        },
    }
    send_failed_count = 0
    for endpoint in endpoints:
        frame = {**frame_base, "ws_frame_id": f"evt_notify_{msg_id_server}_{endpoint.id}"}
        try:
            ok = await ws_manager.send_json(int(endpoint.id), frame)
            if not ok:
                await ws_manager.unregister(int(endpoint.id))
                send_failed_count += 1
                await upsert_delivery(
                    db,
                    msg_id_server=msg_id_server,
                    endpoint=endpoint,
                    status=MessageDeliveryStatus.FAILED,
                    provider_msg_id=None,
                    failed_reason_code="WS_SEND_FAILED",
                    failed_detail="WebSocket endpoint send failed",
                )
                continue

            await upsert_delivery(
                db,
                msg_id_server=msg_id_server,
                endpoint=endpoint,
                status=MessageDeliveryStatus.DISPATCHED,
                provider_msg_id=msg_id_server,
                failed_reason_code=None,
                failed_detail=None,
            )
        except Exception:
            send_failed_count += 1
            await upsert_delivery(
                db,
                msg_id_server=msg_id_server,
                endpoint=endpoint,
                status=MessageDeliveryStatus.FAILED,
                provider_msg_id=None,
                failed_reason_code="WS_SEND_FAILED",
                failed_detail="WebSocket endpoint send failed",
            )
            logger.exception(
                "notification_delivery_send_failed",
                notification_id=notification.id,
                endpoint_id=int(endpoint.id),
            )

    await db.commit()
    await notification_crud.refresh_delivery_progress(
        db,
        notification_id=int(notification.id),
        msg_id_server=msg_id_server,
    )

    if send_failed_count >= len(endpoints):
        await notification_crud.mark_as_failed(
            db,
            notification_id=notification.id,
            error_message="No active websocket endpoint delivery succeeded",
        )
        logger.error(
            "notification_send_failed",
            notification_id=notification.id,
            to_qiao_id=to_qiao_id,
            endpoint_count=len(endpoints),
        )
        return

    logger.info(
        "notification_sent",
        notification_id=notification.id,
        to_qiao_id=to_qiao_id,
        notification_type=notification_type,
        msg_id=msg_id_server,
        endpoint_count=len(endpoints),
        send_failed_count=send_failed_count,
    )
