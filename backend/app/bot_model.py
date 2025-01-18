import asyncio
from datetime import datetime
from typing import Dict, Optional, List
from database import db_manager
from llm_api import LLMClient
from sender import MessageSender

class BotSession:
    def __init__(self, user_id: str, bot_id: str):
        self.user_id = user_id
        self.bot_id = bot_id
        self.message_queue: List[Dict] = []
        self.last_activity = datetime.now()
        self.is_active = True
        self.llm_client = LLMClient()
        self.message_sender = MessageSender()
        self.processing_lock = asyncio.Lock()
        
    async def process_message(self, message: str):
        async with self.processing_lock:
            self.last_activity = datetime.now()
            
            # 保存消息到数据库
            await db_manager.save_message(
                from_user=self.user_id,
                to_user=self.bot_id,
                content=message
            )
            
            # 添加消息到队列
            self.message_queue.append({
                "role": "user",
                "content": message,
                "timestamp": self.last_activity
            })
            
            # 如果队列中有两条或以上的消息，处理它们
            if len(self.message_queue) >= 2:
                await self._process_queue()
    
    async def _process_queue(self):
        try:
            # 获取bot信息和聊天历史
            bot_info = await db_manager.get_bot_info(self.bot_id)
            chat_history = await db_manager.get_chat_history(
                self.user_id, 
                self.bot_id,
                limit=5
            )
            
            # 准备发送给LLM的上下文
            context = {
                "bot_info": bot_info,
                "chat_history": chat_history,
                "current_messages": self.message_queue
            }
            
            # 调用LLM API
            response = await self.llm_client.generate_response(context)
            
            # 保存回复到数据库
            await db_manager.save_message(
                from_user=self.bot_id,
                to_user=self.user_id,
                content=response
            )
            
            # 发送回复
            await self.message_sender.send_message(
                self.user_id,
                response
            )
            
            # 清空消息队列
            self.message_queue.clear()
            
        except Exception as e:
            print(f"Error processing message queue: {e}")
            # 在发生错误时保留消息队列
            await self.message_sender.send_message(
                self.user_id,
                "Sorry, I encountered an error processing your message."
            )
    
    async def check_timeout(self):
        while self.is_active:
            await asyncio.sleep(60)  # 每分钟检查一次
            if (datetime.now() - self.last_activity).seconds > 600:  # 10分钟超时
                self.is_active = False
                await self.cleanup()
                break
    
    async def cleanup(self):
        # 清理资源
        if self.message_queue:
            await self._process_queue()
        await db_manager.close_session()

class BotManager:
    def __init__(self, message_sender):
        self.sessions: Dict[str, BotSession] = {}
        self.message_sender = message_sender
    
    async def get_or_create_session(self, user_id: str, bot_id: str) -> BotSession:
        session_key = f"{user_id}:{bot_id}"
        if session_key not in self.sessions or not self.sessions[session_key].is_active:
            session = BotSession(user_id, bot_id)
            session.message_sender = self.message_sender
            self.sessions[session_key] = session
            asyncio.create_task(session.check_timeout())
        return self.sessions[session_key]
    
    async def process_message(self, user_id: str, bot_id: str, message: str):
        session = await self.get_or_create_session(user_id, bot_id)
        await session.process_message(message)