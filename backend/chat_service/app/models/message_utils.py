import logging
from typing import Optional
from datetime import datetime
from event_bus import event_bus, EventTypes

logger = logging.getLogger(__name__)

async def send_message(self, content: Optional[str] = '',message_type: str = 'chat') -> None:
    """
    发送消息
    
    Args:
        self: 模型实例
        content: 消息内容
        message_type: 消息类型
    """
    try:
        message = {
            'from_id': str(self.bot.id),
            'to_id': str(self.bot.user_id),
            'content': str(content),
            'message_type': message_type,
            'message_service': self.message_service,
            'timestamp': datetime.now().isoformat()
        }
        logger.debug(f"Sending {message_type} message from {self.bot.id} to {self.bot.user_id}")
        await event_bus.publish(EventTypes.SEND_MESSAGE, message)
    except Exception as e:
        logger.error(f"Error sending {message_type} message: {str(e)}", exc_info=True)