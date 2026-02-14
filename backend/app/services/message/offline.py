"""Offline message retrieval and acknowledgement service.

Offline provides incremental catch-up for a device after reconnecting.
It does NOT provide history sync.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.enums import MessageType
from app.models.contact import Contact
from app.models.message import MessageDevice, MessageHistory
from app.models.user import User
from app.schemas.message.offline import (
    OfflineMessageAckRequest,
    OfflineMessageItem,
    OfflineMessageItemMetadata,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_LIMIT = 100
MAX_LIMIT = 100
CURSOR_PARTS_COUNT = 2


def _encode_cursor(sent_at_ms: int, msg_id_server: str) -> str:
    raw = f"{sent_at_ms}:{msg_id_server}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[int, str] | None:
    padding = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.urlsafe_b64decode((cursor + padding).encode()).decode()
    except (ValueError, UnicodeDecodeError):
        return None

    parts = decoded.split(":", 1)
    if len(parts) != CURSOR_PARTS_COUNT:
        return None
    try:
        sent_at_ms = int(parts[0])
    except ValueError:
        return None
    msg_id_server = parts[1]
    if not msg_id_server:
        return None
    return sent_at_ms, msg_id_server


def _to_ms(value: datetime | None) -> int | None:
    if value is None:
        return None
    return int(value.timestamp() * 1000)


def _to_datetime(value_ms: int) -> datetime:
    return datetime.fromtimestamp(value_ms / 1000, tz=UTC)


def _build_start_condition(
    model: type[MessageHistory], sent_at: datetime, msg_id_server: str | None
) -> ColumnElement[bool]:
    if msg_id_server:
        return or_(
            model.sent_at > sent_at,
            and_(model.sent_at == sent_at, model.msg_id_server > msg_id_server),
        )
    return model.sent_at > sent_at


async def _get_or_create_device(
    db: AsyncSession, *, user: User, device_id: UUID
) -> tuple[MessageDevice, bool]:
    result = await db.execute(
        select(MessageDevice).where(
            MessageDevice.user_id == user.id,
            MessageDevice.device_id == device_id,
        )
    )
    device = result.scalar_one_or_none()
    if device:
        return device, False

    # Initial cursor: do not backfill history; start from "now".
    now = datetime.now(UTC)
    device = MessageDevice(
        user_id=user.id,
        user_qiao_id=user.qiao_id,
        device_id=device_id,
        last_acked_msg_id=None,
        last_acked_msg_sent_at=now,
        last_pull_at=now,
        last_seen_at=now,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device, True


async def fetch_offline_messages(
    db: AsyncSession,
    *,
    user: User,
    device_id: str,
    limit: int | None,
    cursor: str | None,
) -> tuple[list[OfflineMessageItem], str | None, bool, int]:
    """Fetch offline messages for a device."""
    effective_limit = DEFAULT_LIMIT if limit is None else max(1, min(limit, MAX_LIMIT))

    try:
        device_uuid = UUID(device_id)
    except ValueError as exc:
        raise ValueError("invalid_device_id") from exc

    device, created = await _get_or_create_device(db, user=user, device_id=device_uuid)
    if created:
        return [], None, False, effective_limit

    start_time: datetime | None = device.last_acked_msg_sent_at
    start_msg_id: str | None = device.last_acked_msg_id

    if cursor:
        decoded = _decode_cursor(cursor)
        if not decoded:
            raise ValueError("invalid_cursor")
        sent_at_ms, msg_id_server = decoded
        start_time = _to_datetime(sent_at_ms)
        start_msg_id = msg_id_server

    if start_time is None:
        start_time = datetime.fromtimestamp(0, tz=UTC)

    # Access control: only return messages in contacts owned by this user.
    # NOTE: contact.is_deleted comes from SoftDeleteMixin.
    base_conditions = [
        Contact.user_id == user.id,
        Contact.is_deleted == 0,
        MessageHistory.conversation_id == Contact.conversation_id,
        MessageHistory.sent_at.is_not(None),
        MessageHistory.message_type.in_([MessageType.TEXT.value, MessageType.CHAT_INFO.value]),
        _build_start_condition(MessageHistory, start_time, start_msg_id),
    ]

    result = await db.execute(
        select(MessageHistory)
        .join(Contact, MessageHistory.conversation_id == Contact.conversation_id)
        .where(and_(*base_conditions))
        .order_by(MessageHistory.sent_at.asc(), MessageHistory.msg_id_server.asc())
        .limit(effective_limit + 1)
    )
    rows = list(result.scalars().all())

    has_more = len(rows) > effective_limit
    items = rows[:effective_limit]

    messages: list[OfflineMessageItem] = []
    for message in items:
        metadata = message.message_metadata if isinstance(message.message_metadata, dict) else {}
        client_sent_ms = _to_ms(message.client_sent_at)
        sent_ms = _to_ms(message.sent_at) or 0

        action_val = metadata.get("action")
        action = action_val if isinstance(action_val, dict) else None
        notification_raw = metadata.get("notification_type")
        notification_type = int(notification_raw) if isinstance(notification_raw, int) else None

        messages.append(
            OfflineMessageItem(
                msg_id_server=message.msg_id_server,
                msg_id_client=message.msg_id_client,
                conversation_id=message.conversation_id,
                from_qiao_id=message.from_qiao_id,
                to_qiao_id=message.to_qiao_id,
                content=message.content,
                message_type=message.message_type,
                client_sent_time_ms=client_sent_ms,
                sent_time_ms=sent_ms,
                metadata=OfflineMessageItemMetadata(
                    action=action,
                    notification_type=notification_type,
                ),
            )
        )

    next_cursor = None
    if items:
        last_item = items[-1]
        last_sent_ms = _to_ms(last_item.sent_at)
        if last_sent_ms is not None:
            next_cursor = _encode_cursor(last_sent_ms, last_item.msg_id_server)

    device.last_pull_at = datetime.now(UTC)
    db.add(device)
    await db.commit()
    return messages, next_cursor, has_more, effective_limit


async def ack_offline_message(
    db: AsyncSession,
    *,
    user: User,
    payload: OfflineMessageAckRequest,
) -> None:
    """Acknowledge delivered messages for a device.

    ACK only advances (user_id, device_id) cursor; it does NOT update message_history.
    """
    try:
        device_uuid = UUID(payload.device_id)
    except ValueError as exc:
        raise ValueError("invalid_device_id") from exc

    device_result = await db.execute(
        select(MessageDevice).where(
            MessageDevice.user_id == user.id,
            MessageDevice.device_id == device_uuid,
        )
    )
    device = device_result.scalar_one_or_none()
    if not device:
        raise ValueError("device_not_found")

    # Validate message exists and is visible to the user.
    history_result = await db.execute(
        select(MessageHistory)
        .join(Contact, MessageHistory.conversation_id == Contact.conversation_id)
        .where(
            and_(
                MessageHistory.msg_id_server == payload.last_ack_msg_id,
                Contact.user_id == user.id,
                Contact.is_deleted == 0,
            )
        )
    )
    history = history_result.scalar_one_or_none()
    if not history:
        raise ValueError("ack_message_not_found")

    message_sent_at_ms = _to_ms(history.sent_at)
    if message_sent_at_ms is None:
        raise ValueError("ack_sent_time_missing")

    ack_sent_at = _to_datetime(message_sent_at_ms)
    current_sent_at = device.last_acked_msg_sent_at
    current_msg_id = device.last_acked_msg_id

    if current_sent_at is not None:
        is_ahead = ack_sent_at > current_sent_at or (
            ack_sent_at == current_sent_at and payload.last_ack_msg_id > (current_msg_id or "")
        )
    else:
        is_ahead = True

    if not is_ahead:
        logger.warning(
            "offline_ack_ignored",
            user_qiao_id=user.qiao_id,
            device_id=payload.device_id,
            last_ack_msg_id=payload.last_ack_msg_id,
        )
        return

    device.last_acked_msg_id = payload.last_ack_msg_id
    device.last_acked_msg_sent_at = ack_sent_at
    device.last_seen_at = datetime.now(UTC)
    db.add(device)
    await db.commit()
