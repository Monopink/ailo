import asyncio
from datetime import datetime
from .base import BaseModel
from llm_apis.doubao import DouBaoAPI

class LilyModel(BaseModel):
    def __init__(self, bot: any, db_manager: any):
        super().__init__(bot, db_manager)
        self.llm_api = DouBaoAPI()
        self.min_chars = 50  # 最小字符数要求
        self.char_wait_time = 0.1  # 每个字符的等待时间（秒）

    async def process_message(self, message: dict) -> dict:
        """
        处理接收到的消息
        """
        try:
            # 更新上下文
            self.update_context('last_message', message)
            self.update_context('last_message_time', datetime.now())

            # 检查消息长度
            content = message.get('content', '')
            if len(content) < self.min_chars:
                return {
                    'from_id': str(self.bot.id),
                    'to_id': message['from_id'],
                    'content': f"请多说一些，至少{self.min_chars}个字才能帮助我更好地理解和回复哦~",
                    'message_type': 'prompt'
                }

            # 生成响应
            response = await self.generate_response(message)

            # 模拟思考和打字时间
            thinking_time = len(content) * 0.05  # 思考时间与输入长度相关
            await asyncio.sleep(thinking_time)

            # 保存上下文
            await self.save_context()

            return response

        except Exception as e:
            return {
                'from_id': str(self.bot.id),
                'to_id': message['from_id'],
                'content': f"抱歉，处理消息时出现错误: {str(e)}",
                'message_type': 'error'
            }

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
                'short_term_memory': self.context.get('short_term_memory', '')
            }

            # 调用 LLM API 生成回复
            llm_response = await self.llm_api.generate_response(
                message['content'],
                context
            )

            # 模拟打字延迟
            typing_delay = len(llm_response) * self.char_wait_time
            await asyncio.sleep(typing_delay)

            response = {
                'from_id': str(self.bot.id),
                'to_id': message['from_id'],
                'content': llm_response,
                'message_type': 'text',
                'metadata': {
                    'relationship_type': self.bot.relationship_type.value,
                    'relationship_score': self.bot.relationship_score,
                }
            }

            return response

        except Exception as e:
            return {
                'from_id': str(self.bot.id),
                'to_id': message['from_id'],
                'content': "抱歉，生成回复时出现错误。",
                'message_type': 'error'
            }

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