import logging
import datetime

logger = logging.getLogger(__name__)

def convert_timestamp(self, timestamp: str|None=None) -> str:
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
        hours, minutes = map(int, self.time_zone.replace('+', '').split(':'))
        
        if timestamp is None:
            # 使用当前UTC时间
            utc_time = datetime.datetime.now(datetime.timezone.utc)
        else:
            # 解析UTC时间戳
            utc_time = datetime.datetime.strptime(timestamp.replace('Z', '+00:00'), 
                                                '%Y-%m-%dT%H:%M:%S.%f%z')
        
        # 应用时区偏移
        local_time = utc_time + datetime.timedelta(hours=hours, minutes=minutes)
        # 格式化输出
        return local_time.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        logger.error(f"ValueError in _convert_timestamp: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in _convert_timestamp: {str(e)}")
        raise

async def trim_context(self) -> None:
    """修剪上下文"""
    pass

async def trim_memory(self) -> None:
    """修剪记忆"""
    pass

def refresh_system_context(self) -> None:
    """刷新系统上下文"""
    try:
        # 检查并更新关系类型对应的风格
        if self.relationship_type != self.bot.relationship_type.value:
            self.style = getattr(self.bot, f"{self.relationship_type}_style", '') if self.relationship_type else ''
            logger.info(f"Updated relationship style for bot {self.bot.id}")

        # 构建新的系统上下文
        system_context_content = (
            f"{self.default_system_context}\n"
            f"{self.style}\n"
            f"{self.memory}"
        )
        new_system_context = {"role": "system", "content": system_context_content}

        # 更新context中的系统消息
        if 'messages' in self.context and self.context['messages']:
            self.context['messages'][0] = new_system_context
        else:
            self.context['messages'] = [new_system_context]
        
        logger.debug(f"System context refreshed for bot {self.bot.id}")
    except Exception as e:
        logger.error(f"Error refreshing system context for bot {self.bot.id}: {str(e)}", exc_info=True)

def varify_context(self) -> None:
    """验证上下文结构并初始化如果需要"""
    try:
        is_valid = (
            isinstance(self.context, dict) and
            'messages' in self.context and
            isinstance(self.context['messages'], list) and
            self.context['messages'] and
            all(isinstance(msg, dict) and 'role' in msg and 'content' in msg 
                for msg in self.context['messages'])
        )

        if not is_valid:
            logger.warning(f"Invalid context structure detected for bot {self.bot.id}, initializing new context")
            self.context = {'messages': []}
            self._refresh_system_context()
        
        logger.debug(f"Context structure verified for bot {self.bot.id}")
    except Exception as e:
        logger.error(f"Error verifying context for bot {self.bot.id}: {str(e)}", exc_info=True)
        # 在发生错误时也初始化上下文
        self.context = {'messages': []}
        self._refresh_system_context()

def append_context(self, role: str, context_content: str) -> None:
    """
    追加或合并上下文消息
    
    Args:
        role: 消息角色 ('system', 'user', 或 'assistant')
        context_content: 消息内容
    """
    try:
        # 添加时间戳到消息内容
        timestamp = self._convert_timestamp()
        formatted_content = f"[{timestamp}]\n{context_content}"

        # 构造新消息
        new_message = {
            "role": role,
            "content": formatted_content
        }

        # 获取最后一条消息
        last_message = self.context['messages'][-1]

        # 检查角色是否相同
        if last_message['role'] == role:
            # 合并消息内容
            merged_content = f"{last_message['content']}\n{formatted_content}"
            last_message['content'] = merged_content
            logger.debug(f"Merged message with same role for bot {self.bot.id}")
        else:
            # 添加新消息
            self.context['messages'].append(new_message)
            logger.debug(f"Added new message with different role for bot {self.bot.id}")

    except Exception as e:
        logger.error(f"Error appending context for bot {self.bot.id}: {str(e)}", exc_info=True)
        # 在发生错误时确保context结构完整
        if not self.context or 'messages' not in self.context:
            self._varify_context()
            self._append_context(role, context_content)
            logger.error(f"Reset context structure for bot {self.bot.id} after error")

def remove_last_context(self) -> None:
    """删除最后一条上下文消息"""
    try:
        if (self.context.get('messages') and 
            len(self.context['messages']) > 1):  # 确保至少保留系统消息
            self.context['messages'].pop()
            logger.debug(f"Removed last context message for bot {self.bot.id}")
        else:
            logger.warning(f"No message to remove or only system message remains for bot {self.bot.id}")
    except Exception as e:
        logger.error(f"Error removing last context for bot {self.bot.id}: {str(e)}", exc_info=True)