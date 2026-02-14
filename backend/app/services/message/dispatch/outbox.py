"""Outbox enqueue helpers for message timeline dispatch."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import MessageDispatchOutboxStatus, MessageDispatchOutboxType
from app.models.message import MessageDispatchOutbox
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)


async def enqueue_timeline_fanout(
    db: AsyncSession,
    *,
    msg_id_server: str,
    owner_user_id: int,
) -> None:
    """Insert timeline fanout task into outbox (idempotent by unique key)."""
    try:
        async with db.begin_nested():
            db.add(
                MessageDispatchOutbox(
                    id=generate_snowflake_id(),
                    outbox_type=MessageDispatchOutboxType.TIMELINE_FANOUT,
                    msg_id_server=msg_id_server,
                    owner_user_id=owner_user_id,
                    status=MessageDispatchOutboxStatus.PENDING,
                    attempt_count=0,
                    next_retry_at=None,
                    locked_at=None,
                    last_error_code=None,
                    last_error_detail=None,
                )
            )
            await db.flush()
    except IntegrityError:
        logger.debug(
            "dispatch_outbox_already_exists",
            msg_id_server=msg_id_server,
            owner_user_id=owner_user_id,
        )
