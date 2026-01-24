"""Offline message retrieval and acknowledgement service."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.crud.message import message as message_crud
from app.crud.message import offline_cursor as offline_cursor_crud
from app.enums import MessageStatus
from app.models.message.message import MessageHistory
from app.models.message.offline_cursor import MessageOfflineCursor
from app.models.user import User
from app.schemas.message.offline import (
    OfflineCursorCreate,
    OfflineMessageAckRequest,
    OfflineMessageItem,
)
from app.type_defs import JSONDict, JSONValue
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


def _extract_metadata_field(
    metadata: JSONDict | None,
    key: str,
    expected_type: type | tuple[type, ...],
) -> JSONValue | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    return value if isinstance(value, expected_type) else None


async def _get_or_create_cursor(
    db: AsyncSession, *, user: User, device_id: str
) -> tuple[MessageOfflineCursor, bool]:
    cursor = await offline_cursor_crud.get_by_user_and_device(
        db, user_id=user.id, device_id=device_id
    )
    if cursor:
        return cursor, False

    now = datetime.now(UTC)
    cursor = await offline_cursor_crud.create(
        db,
        obj_in=OfflineCursorCreate(
            user_id=user.id,
            user_qiao_id=user.qiao_id,
            device_id=device_id,
            last_ack_sent_at=now,
            last_pull_at=now,
        ),
    )
    return cursor, True


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
    offline_cursor, created = await _get_or_create_cursor(db, user=user, device_id=device_id)

    if created:
        return [], None, False, effective_limit

    start_time: datetime | None = offline_cursor.last_ack_sent_at
    start_msg_id: str | None = offline_cursor.last_ack_msg_id

    if cursor:
        decoded = _decode_cursor(cursor)
        if not decoded:
            raise ValueError("invalid_cursor")
        sent_at_ms, msg_id_server = decoded
        start_time = _to_datetime(sent_at_ms)
        start_msg_id = msg_id_server

    if start_time is None:
        start_time = datetime.fromtimestamp(0, tz=UTC)

    base_conditions = [
        MessageHistory.to_qiao_id == user.qiao_id,
        MessageHistory.sent_at.is_not(None),
        _build_start_condition(MessageHistory, start_time, start_msg_id),
    ]

    result = await db.execute(
        select(MessageHistory)
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
        sent_ms = _to_ms(message.sent_at) or 0
        server_ms = _to_ms(message.created_at) or sent_ms
        action_value = _extract_metadata_field(metadata, "action", dict)
        action = action_value if isinstance(action_value, dict) else None
        notification_raw = _extract_metadata_field(metadata, "notification_type", (int, float))
        notification_type = (
            int(notification_raw) if isinstance(notification_raw, int | float) else None
        )

        messages.append(
            OfflineMessageItem(
                msg_id_server=message.msg_id_server,
                msg_id_client=message.msg_id_client,
                conv_id=message.conversation_id,
                from_qiao_id=message.from_qiao_id,
                to_qiao_id=message.to_qiao_id,
                content=message.content,
                message_type=message.message_type,
                sent_time=sent_ms,
                server_time=server_ms,
                action=action,
                notification_type=notification_type,
                data=None,
            )
        )

    next_cursor = None
    if items:
        last_item = items[-1]
        last_sent_ms = _to_ms(last_item.sent_at)
        if last_sent_ms is not None:
            next_cursor = _encode_cursor(last_sent_ms, last_item.msg_id_server)

    await offline_cursor_crud.touch_last_pull(db, cursor=offline_cursor)
    return messages, next_cursor, has_more, effective_limit


async def ack_offline_message(
    db: AsyncSession,
    *,
    user: User,
    payload: OfflineMessageAckRequest,
) -> None:
    """Acknowledge delivered messages for a device."""
    cursor = await offline_cursor_crud.get_by_user_and_device(
        db, user_id=user.id, device_id=payload.device_id
    )
    if not cursor:
        raise ValueError("cursor_not_found")

    message = await message_crud.get_by_server_id(db, msg_id_server=payload.last_ack_msg_id)
    if not message or message.to_qiao_id != user.qiao_id:
        raise ValueError("ack_message_not_found")

    message_sent_at_ms = _to_ms(message.sent_at)
    if message_sent_at_ms is None:
        raise ValueError("ack_sent_time_missing")
    if message_sent_at_ms != payload.last_ack_sent_at:
        logger.warning(
            "offline_ack_sent_time_mismatch",
            msg_id_server=payload.last_ack_msg_id,
            provided_sent_at=payload.last_ack_sent_at,
            stored_sent_at=message_sent_at_ms,
        )
    ack_sent_at = _to_datetime(message_sent_at_ms)
    current_sent_at = cursor.last_ack_sent_at
    current_msg_id = cursor.last_ack_msg_id

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
            last_ack_sent_at=payload.last_ack_sent_at,
        )
        return

    target_sent_at = ack_sent_at
    target_msg_id = payload.last_ack_msg_id
    await db.execute(
        update(MessageHistory)
        .where(
            and_(
                MessageHistory.to_qiao_id == user.qiao_id,
                MessageHistory.sent_at.is_not(None),
                or_(
                    MessageHistory.sent_at < target_sent_at,
                    and_(
                        MessageHistory.sent_at == target_sent_at,
                        MessageHistory.msg_id_server <= target_msg_id,
                    ),
                ),
                MessageHistory.status != MessageStatus.DELIVERED,
            )
        )
        .values(status=MessageStatus.DELIVERED)
    )

    cursor.last_ack_msg_id = payload.last_ack_msg_id
    cursor.last_ack_sent_at = ack_sent_at
    db.add(cursor)
    await db.commit()
    await db.refresh(cursor)
