import asyncio
import logging
from datetime import datetime
from .base import BaseModel
from event_bus import event_bus, EventTypes
from llm_apis.mirrored_llm import MirroredLLMAPI as LLMAPI
import json

logger = logging.getLogger(__name__)

class LilyModel(BaseModel):
    def __init__(self, bot: any, db_manager: any):
        super().__init__(bot, db_manager)
        self.llm_api = LLMAPI()
        self.min_chars = 0  # 最小字符数要求
        self.char_wait_time = 0.05  # 每个字符的等待时间（秒）
        self.inactivity_timeout = 20  # x秒无消息超时
        self.cleanup_task = None
        # 添加唤醒消息标志
        self.update_context('is_wake_message', True)

    def _reset_cleanup_timer(self):
        """重置清理定时器"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
        self.cleanup_task = asyncio.create_task(self._schedule_cleanup())

    async def process_message(self, message: dict) -> dict:
        """
        处理接收到的消息
        """
        try:
            # 重置清理定时器
            self._reset_cleanup_timer()

            # 检查是否是首次消息
            is_initial = self.context.get('is_wake_message', True)
            
            # 更新上下文
            self.update_context('last_message', message)
            self.update_context('last_message_time', datetime.now())
            self.update_context('is_wake_message', False)  # 设置标志为False

            # 检查消息长度
            content = message.get('content', '')
            if len(content) < self.min_chars:
                response_content = "[Wake] " + "[Message received]" if is_initial else "[Message received]"
                return {
                    'from_id': str(self.bot.id),
                    'to_id': message['from_id'],
                    'content': response_content,
                    'message_type': 'prompt'
                }

            # 生成响应
            response = await self.generate_response(message)
            
            # 如果是唤醒消息，在响应内容前添加[Wake]标记
            if is_initial:
                response['message'] = "[Wake] " + response['message']

            # 模拟思考和打字时间
            thinking_time = len(content) * self.char_wait_time  # 思考时间与输入长度相关
            await asyncio.sleep(thinking_time)

            response = {
                'from_id': str(self.bot.id),
                'to_id': message['from_id'],
                'content': json.dumps(response, ensure_ascii=False, indent=2),  # 使用ensure_ascii=False显示中文,indent=2增加缩进
                'message_type': 'text',
                'meta_data': {
                    'relationship_type': self.bot.relationship_type.value,
                    'relationship_score': self.bot.relationship_score,
                }
            }

            # 保存上下文
            await self.save_context()

            return response

        except Exception as e:
            if self.cleanup_task:
                self.cleanup_task.cancel()
            logger.error(f"Error processing message: {str(e)}")

    async def generate_response(self, message: dict) -> dict:
        """
        生成响应消息
        """
        try:
            # 获取 bot 的性格风格
            style = getattr(self.bot, f"{self.bot.relationship_type.value}_style", "")
            
            # 构建上下文信息
            context = {
                'bot_name': f"Bot_{self.bot.id}",
                'user_id': message['from_id'],
                'relationship_type': self.bot.relationship_type.value,
                'relationship_score': self.bot.relationship_score,
                'style': style,
                'long_term_memory': self.bot.long_term_memory,
                'short_term_memory': self.context.get('short_term_memory', ''),
                'message': message['content']
            }

            logger.debug(f"Send context to LLM: {context}")

            # 调用 LLM API 生成回复
            llm_response = await self.llm_api.generate_response(context)

            return llm_response

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")

    async def save_context(self):
        """
        保存上下文到数据库
        """
        session_data = {
            'last_activity': datetime.now(),
            'context': self.context,
            'status': 'active'
        }
        
        # 更新会话信息
        session_id = f"{self.bot.id}_{self.context['last_message']['from_id']}"
        await self.db_manager.update_session(session_id, session_data)

    async def _schedule_cleanup(self):
        """调度清理任务"""
        try:
            await asyncio.sleep(self.inactivity_timeout)
            await self.cleanup()
            # 发布会话结束事件
            await event_bus.publish(
                EventTypes.SESSION_ENDED,
                {
                    'bot_id': str(self.bot.id),
                    'user_id': self.context.get('last_message', {}).get('from_id'),
                    'reason': 'inactivity_timeout'
                }
            )
        except asyncio.CancelledError:
            logger.debug(f"Cleanup task for bot {self.bot.id} cancelled")

    async def cleanup(self):
        """清理实例前的操作"""
        logger.info(f"Starting cleanup for bot {self.bot.id}")
        # await self.save_context()
        if self.cleanup_task:
            logger.debug(f"Cancelling cleanup task for bot {self.bot.id}")
            self.cleanup_task.cancel()
            self.cleanup_task = None
            logger.info(f"Cleanup completed for bot {self.bot.id}")