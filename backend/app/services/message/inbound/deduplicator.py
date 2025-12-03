"""
Inbound message deduplicator (business layer).

Handles message deduplication logic.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.message import message as message_crud
from app.services.message.schemas import InboundMessageEvent
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def is_duplicate(db: AsyncSession, event: InboundMessageEvent) -> bool:
    """
    Check if message is duplicate.

    Business layer responsibility:
    - Check against message_history by client_msg_id

    Args:
        db: Database session
        event: InboundMessageEvent

    Returns:
        True if duplicate, False otherwise
    """
    if not event.msg_id_client:
        return False

    existing = await message_crud.get_by_conversation_and_client_id(
        db,
        conversation_id=event.conversation_id,
        msg_id_client=event.msg_id_client,
    )

    if existing:
        logger.info(
            "duplicate_message",
            msg_id_client=event.msg_id_client,
            conv_id=event.conversation_id,
        )
        return True

    return False
