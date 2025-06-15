import logging
from typing import Optional
from datetime import datetime

from enums import MessageType
from event_bus import event_bus, EventTypes

logger = logging.getLogger(__name__)


async def send_message(
    self, content: Optional[str] = "", message_type: str = MessageType.CHAT.name
) -> None:
    """Send message
    Args:
        self: Model instance
        content: Message content
        message_type: Message type
    """
    try:
        message = {
            "from_entity": str(self.bot.entity_id),
            "to_entity": str(self.bot.user_entity_id),
            "content": str(content),
            "message_type": message_type,
            "message_service": self.message_service,
            "message_time": datetime.now().isoformat(),
        }
        logger.debug(
            f"Sending {message_type} message from {self.bot.id}"
            f"that entity_id is {self.bot.entity_id} to {self.bot.user_entity_id}"
        )
        await event_bus.publish(EventTypes.SEND_MESSAGE, message)
    except Exception as e:
        logger.error(f"Error sending {message_type} message: {str(e)}", exc_info=True)
