"""
Inbound message router (business layer).

Routes messages to appropriate handlers.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.contact import contact as contact_crud
from app.enums import MessageType
from app.models.message import MessageHistory
from app.services.message.dispatch.outbox import enqueue_timeline_fanout
from app.services.message.dispatch.realtime import fanout_typing_event
from app.services.message.processing import buffer
from app.services.message.schemas import InboundMessageEvent
from app.services.message.storage.persistence import store_message
from app.utils.logging import get_logger
from app.utils.snowflake import generate_snowflake_id

logger = get_logger(__name__)


CONTACT_TYPE_AI = 2
_TIMELINE_MESSAGE_TYPES = {MessageType.TEXT, MessageType.CHAT_INFO}
_TYPING_MESSAGE_TYPES = {MessageType.TYPING_START, MessageType.TYPING_END}


async def route_message(db: AsyncSession, event: InboundMessageEvent) -> MessageHistory | None:
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
        contact = await contact_crud.get_by_conversation_id(
            db, conversation_id=event.conversation_id
        )
        if not contact:
            logger.error("contact_not_found_in_router", conversation_id=event.conversation_id)
            return None

        # Determine if message is for AI
        is_for_ai = contact.contact_type == CONTACT_TYPE_AI
        is_buffer_event = event.message_type in (
            MessageType.TEXT,
            MessageType.TYPING_START,
            MessageType.TYPING_END,
        )

        # Store to message_history (typing events are filtered inside store_message).
        stored = await store_message(db, event, contact=contact)

        if (
            stored is not None
            and event.message_type in _TIMELINE_MESSAGE_TYPES
            and isinstance(contact.user_id, int)
        ):
            await enqueue_timeline_fanout(
                db,
                msg_id_server=stored.msg_id_server,
                owner_user_id=contact.user_id,
            )

        if event.message_type in _TYPING_MESSAGE_TYPES and isinstance(contact.user_id, int):
            typing_state = "start" if event.message_type == MessageType.TYPING_START else "end"
            await fanout_typing_event(
                db,
                owner_user_id=contact.user_id,
                conversation_id=contact.conversation_id,
                from_qiao_id=event.from_qiao_id,
                to_qiao_id=event.to_qiao_id,
                typing_state=typing_state,
                time_ms=event.sent_at_ms,
            )

        # Route to AI handler if needed (after persistence, so ws ack can be stable).
        if is_for_ai and is_buffer_event:
            logger.info(
                "routing_to_ai",
                conversation_id=contact.conversation_id,
                contact_qiao_id=contact.contact_qiao_id,
            )

            try:
                await buffer.add_message_to_buffer(
                    db=db,
                    event=event,
                    instance_qiao_id=contact.contact_qiao_id,
                )
                logger.info("message_buffered", conversation_id=contact.conversation_id)
            except Exception as e:
                logger.error(
                    "buffer_add_failed",
                    error=str(e),
                    conversation_id=contact.conversation_id,
                )

        logger.info(
            "message_routed",
            msg_id_server=msg_id_server,
            conversation_id=contact.conversation_id,
            is_for_ai=is_for_ai,
        )
        return stored

    except Exception as e:
        logger.error("route_message_error", error=str(e), exc_info=True)
        raise
