from typing import Optional
from datetime import datetime

from enums import MessageType
from event_bus import event_bus, EventTypes


async def send_message(
    self, content: Optional[str] = "", message_type: str = MessageType.CHAT.name
) -> None:
    try:
        message = {
            "from_entity": str(self.bot.entity_id),
            "to_entity": str(self.bot.user_entity_id),
            "content": str(content),
            "message_type": message_type,
            "message_service": self.message_service,
            "message_time": datetime.now().isoformat(),
        }
        self.logger.info(
            "sending_message",
            message_type=message_type,
            has_content=bool(content),
            from_entity=self.bot.entity_id,
            to_entity=self.bot.user_entity_id,
        )
        await event_bus.publish(EventTypes.SEND_MESSAGE, message)
    except Exception as e:
        self.logger.error("message_send_error", message_type=message_type, error=str(e), exc_info=True)
