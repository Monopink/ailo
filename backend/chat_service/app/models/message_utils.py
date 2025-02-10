import logging
from typing import Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from event_bus import event_bus, EventTypes

logger = logging.getLogger(__name__)


def convert_timestamp(self, timestamp: str | None = None) -> str:
    """将UTC时间戳转换为指定时区的时间字符串
    Args:
        timestamp: ISO格式的UTC时间戳 (例如: '2025-02-01T07:17:33.564Z')，
                  如果为None则使用当前时间
    Returns:
        转换后的时间字符串 (例如: '2025-02-01 07:17:35')
    """
    try:
        # 获取时区对象
        timezone_obj = ZoneInfo(self.bot.time_zone)

        if timestamp is None:
            # 使用当前UTC时间
            utc_time = datetime.now(timezone.utc)
        else:
            # 解析UTC时间戳
            utc_time = datetime.strptime(
                timestamp.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S.%f%z"
            )

        # 转换到目标时区
        local_time = utc_time.astimezone(timezone_obj)
        # 格式化输出
        return local_time.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        logger.error(f"ValueError in convert_timestamp: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in convert_timestamp: {str(e)}")
        raise


async def send_message(
    self, content: Optional[str] = "", message_type: str = "chat"
) -> None:
    """发送消息
    Args:
        self: 模型实例
        content: 消息内容
        message_type: 消息类型
    """
    try:
        message = {
            "from_entity": str(self.bot.entity_id),
            "to_entity": str(self.bot.user_entity_id),
            "content": str(content),
            "message_type": message_type,
            "message_service": self.message_service,
            "timestamp": datetime.now().isoformat(),
        }
        logger.debug(
            f"Sending {message_type} message from {self.bot.id} that entity_id is {self.bot.entity_id} to {self.bot.user_entity_id}"
        )
        await event_bus.publish(EventTypes.SEND_MESSAGE, message)
    except Exception as e:
        logger.error(f"Error sending {message_type} message: {str(e)}", exc_info=True)
