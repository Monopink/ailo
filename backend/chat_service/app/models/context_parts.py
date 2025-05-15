import logging
from zhdate import ZhDate
from datetime import datetime
from .context_strategy import ContextComponents, ContextStrategyFactory

logger = logging.getLogger(__name__)


async def trim_context(self) -> None:
    """修剪上下文"""
    pass


async def trim_memory(self) -> None:
    """修剪记忆"""
    pass


def create_instant_context(self) -> str:
    """创建即时上下文，包含当前时间、基本状态信息以及农历信息
    Returns:
        str: 格式化的即时上下文字符串
    """
    try:
        # 使用 _convert_timestamp 获取 bot 时区的当前时间
        current_time = self._convert_timestamp()

        # 将当前时间字符串解析为 datetime 对象（假定时间格式为 '%Y-%m-%d %H:%M:%S'）
        dt_current = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
        weekday_str = [
            "星期一",
            "星期二",
            "星期三",
            "星期四",
            "星期五",
            "星期六",
            "星期日",
        ][dt_current.weekday()]

        # 根据时间判断时间段
        hour = int(current_time.split()[1].split(":")[0])
        if 0 <= hour < 6:
            time_period = "凌晨"
        elif 6 <= hour < 9:
            time_period = "早上"
        elif 9 <= hour < 12:
            time_period = "上午"
        elif 12 <= hour < 14:
            time_period = "中午"
        elif 14 <= hour < 18:
            time_period = "下午"
        elif 18 <= hour < 24:
            time_period = "晚上"
        else:
            time_period = "未知时间"

        # 使用 zhdate 库获取农历信息
        lunar_info = ZhDate.from_datetime(dt_current).chinese()

        # 构建即时上下文，增加了今天是星期几以及农历信息chrome-extension://mpognobbkildjkofajifpdfhcoklimli/components/private-intro/private-intro.html
        instant_context = (
            f"现在是{current_time}，{time_period}，{weekday_str}。\n"
            f"农历：{lunar_info}。\n"
            f"你在{self.bot.city_name if hasattr(self.bot, 'city_name') else '某市'}。"
        )

        logger.debug(f"Created instant context with time: {instant_context}")
        return instant_context

    except Exception as e:
        logger.error(f"Error creating instant context: {str(e)}", exc_info=True)
        return "当前状态未知。"


def refresh_system_context(self) -> None:
    """刷新系统上下文"""
    try:
        # 获取即时上下文
        self.instant_context = self._create_instant_context()

        # 创建 ContextComponents 实例
        components = ContextComponents()

        # 设置属性而不是通过构造函数
        components.info = self.bot.info
        components.styles = self.bot.styles
        components.memory = self.memory
        components.instant_context = self.instant_context
        components.message_tag = self.message_tag

        # 创建上下文策略
        system_prompt, strategy = ContextStrategyFactory.create(
            relationship_type=self.relationship_type,
            components=components,
            include_summary=self.need_summary,
        )

        new_system_context = {"role": "system", "content": system_prompt}
        logger.debug(f"New system context: {new_system_context}")

        # 更新context中的系统消息
        if "messages" in self.context and self.context["messages"]:
            self.context["messages"][0] = new_system_context
        else:
            self.context["messages"] = [new_system_context]

    except Exception as e:
        logger.error(f"Error refreshing system context: {str(e)}", exc_info=True)
        raise


def varify_context(self) -> None:
    """验证上下文结构并初始化如果需要"""
    try:
        is_valid = (
            isinstance(self.context, dict)
            and "messages" in self.context
            and isinstance(self.context["messages"], list)
            and self.context["messages"]
            and all(
                isinstance(msg, dict) and "role" in msg and "content" in msg
                for msg in self.context["messages"]
            )
        )

        if not is_valid:
            logger.warning(
                f"Invalid context structure detected for bot {self.bot.id}, initializing new context"
            )
            self.context = {"messages": []}
            self._refresh_system_context()

        logger.debug(f"Context structure verified for bot {self.bot.id}")
    except Exception as e:
        logger.error(
            f"Error verifying context for bot {self.bot.id}: {str(e)}", exc_info=True
        )
        # 在发生错误时也初始化上下文
        self.context = {"messages": []}
        # self._refresh_system_context()


def append_context(self, role: str, context_content: str) -> None:
    """追加或合并上下文消息

    Args:
        role: 消息角色 ('system', 'user', 或 'assistant')
        context_content: 消息内容
        timestamp: 消息时间戳
    """
    try:
        # 构造新消息
        new_message = {"role": role, "content": context_content}

        # 获取最后一条消息
        last_message = self.context["messages"][-1]

        # 检查角色是否相同
        if last_message["role"] == role:
            # 合并消息内容
            merged_content = f"{last_message['content']}\n{context_content}"
            last_message["content"] = merged_content
            logger.debug(
                f"Merged message {merged_content} with same role for bot {self.bot.id}"
            )
        else:
            # 添加新消息
            self.context["messages"].append(new_message)
            logger.debug(
                f"Added new message {new_message} with different role for bot {self.bot.id}"
            )

        logger.debug(f"Current context: {self.context}")

    except Exception as e:
        logger.error(
            f"Error appending context for bot {self.bot.id}: {str(e)}", exc_info=True
        )
        # 在发生错误时确保context结构完整
        if not self.context or "messages" not in self.context:
            self._varify_context()
            self._append_context(role, context_content)
            logger.error(f"Reset context structure for bot {self.bot.id} after error")


def remove_last_context(self) -> None:
    """删除最后一条上下文消息"""
    try:
        if (
            self.context.get("messages") and len(self.context["messages"]) > 1
        ):  # 确保至少保留系统消息
            self.context["messages"].pop()
            logger.debug(f"Removed last context message for bot {self.bot.id}")
        else:
            logger.warning(
                f"No message to remove or only system message remains for bot {self.bot.id}"
            )
    except Exception as e:
        logger.error(
            f"Error removing last context for bot {self.bot.id}: {str(e)}",
            exc_info=True,
        )
