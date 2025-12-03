"""
Inbound message validator (business layer).

Validates messages against business rules.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.contact import contact as contact_crud
from app.services.message.schemas import InboundMessageEvent
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def validate_message(db: AsyncSession, event: InboundMessageEvent) -> bool:
    """
    Validate message against business rules.

    Business layer responsibility:
    - Verify conversation exists
    - Check permissions (future)
    - Validate business constraints

    Args:
        db: Database session
        event: InboundMessageEvent

    Returns:
        True if valid, False otherwise
    """
    # Verify conversation exists in contacts table
    contact = await contact_crud.get_by_conv_id(db, conv_id=event.conversation_id)
    if not contact:
        logger.warning("conversation_not_found", conv_id=event.conversation_id)
        return False

    return True
