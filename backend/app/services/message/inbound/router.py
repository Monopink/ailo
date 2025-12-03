"""
Inbound message router (business layer).

Routes messages to appropriate handlers.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.contact import contact as contact_crud
from app.enums import MessageType
from app.services.message.processing import buffer
from app.services.message.schemas import InboundMessageEvent
from app.services.message.storage.persistence import store_message
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)


async def route_message(db: AsyncSession, event: InboundMessageEvent) -> None:
    """
    Route message to appropriate handler.

    Business layer responsibility:
    - Generate msg_id_server
    - Determine routing (AI vs storage only)
    - Invoke appropriate handlers

    Args:
        db: Database session
        event: InboundMessageEvent
    """
    try:
        # Generate server message ID
        msg_id_server = f"msg_{generate_snowflake_id()}"
        event = event.model_copy(update={"msg_id_server": msg_id_server})

        # Get contact info
        contact = await contact_crud.get_by_conv_id(db, conv_id=event.conversation_id)
        if not contact:
            logger.error("contact_not_found_in_router", conv_id=event.conversation_id)
            return

        # Determine if message is for AI
        is_for_ai = contact.contact_type == 2  # 2 = AI
        is_buffer_event = event.message_type in (
            MessageType.TEXT,
            MessageType.TYPING_START,
            MessageType.TYPING_END,
        )

        # Route to AI handler if needed
        if is_for_ai and is_buffer_event:
            logger.info(
                "routing_to_ai",
                conv_id=contact.conv_id,
                contact_qiao_id=contact.contact_qiao_id,
            )

            try:
                await buffer.add_message_to_buffer(
                    db=db,
                    event=event,
                    instance_qiao_id=contact.contact_qiao_id,
                )
                logger.info("message_buffered", conv_id=contact.conv_id)
            except Exception as e:
                logger.error("buffer_add_failed", error=str(e), conv_id=contact.conv_id)

        # Store to message_history
        await store_message(db, event)

        logger.info(
            "message_routed",
            msg_id_server=msg_id_server,
            conv_id=contact.conv_id,
            is_for_ai=is_for_ai,
        )

    except Exception as e:
        logger.error("route_message_error", error=str(e), exc_info=True)
        raise
