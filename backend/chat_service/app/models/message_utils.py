import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from event_bus import event_bus, EventTypes

logger = logging.getLogger(__name__)


def convert_timestamp(self, timestamp: str | None = None) -> str:
    """
    将UTC时间戳转换为指定时区的时间字符串
    Args:
        timestamp: ISO格式的UTC时间戳 (例如: '2025-02-01T07:17:33.564Z')，
                  如果为None则使用当前时间
    Returns:
        转换后的时间字符串 (例如: '2025-02-01 07:17:35')
    """
    try:
        # 解析时区偏移
        hours, minutes = map(int, self.time_zone.replace("+", "").split(":"))

        if timestamp is None:
            # 使用当前UTC时间
            utc_time = datetime.now(timezone.utc)
        else:
            # 解析UTC时间戳
            utc_time = datetime.strptime(
                timestamp.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S.%f%z"
            )

        # 应用时区偏移
        local_time = utc_time + timedelta(hours=hours, minutes=minutes)
        # 格式化输出
        return local_time.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        logger.error(f"ValueError in _convert_timestamp: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in _convert_timestamp: {str(e)}")
        raise


async def send_message(
    self, content: Optional[str] = "", message_type: str = "chat"
) -> None:
    """
    发送消息

    Args:
        self: 模型实例
        content: 消息内容
        message_type: 消息类型
    """
    try:
        message = {
            "from_id": str(self.bot.id),
            "to_id": str(self.bot.user_id),
            "content": str(content),
            "message_type": message_type,
            "message_service": self.message_service,
            "timestamp": datetime.now().isoformat(),
        }
        logger.debug(
            f"Sending {message_type} message from {self.bot.id} to {self.bot.user_id}"
        )
        await event_bus.publish(EventTypes.SEND_MESSAGE, message)
    except Exception as e:
        logger.error(f"Error sending {message_type} message: {str(e)}", exc_info=True)
