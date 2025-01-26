import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Callable, Optional, Dict
from .base import BaseModel
from event_bus import event_bus, EventTypes
from llm_apis.mock_llm import MockLLMAPI as LLMAPI
from db_managers import db_manager
import json

logger = logging.getLogger(__name__)

class LilyModel(BaseModel):
    def __init__(self, bot: Any, cleanup_callback: Callable[[], None]):
        """
        初始化 Lily 模型
        Args:
            bot: Bot 实例
            cleanup_callback: 清理回调函数
        """
        # 调用父类的初始化方法
        super().__init__(bot=bot, cleanup_callback=cleanup_callback)
        
        # Lily 特定的初始化
        self.llm_api = LLMAPI()
        self.process_delay_time = 3  # 等待新消息的延迟时间
        self.process_wait_time = 0   # 处理消息前的等待时间
        self.typing_speed = 0.05     # 打字速度
        self.sleep_timeout = 20      # 睡眠超时时间
        self.is_awake = False        # bot是否苏醒
        self.is_processing = False    # 处理状态
        self.message_queue = asyncio.Queue() # 消息队列
        self.processing_lock = asyncio.Lock() # 处理锁
        self.processing_task = asyncio.create_task(self._process_message_queue()) # 启动消息处理循环
        self.sleep_task = None # 睡眠任务

        # 上下文相关的初始化
        self.context_limit = 1000 # 上下文限制
        self.important_context_limit = 1000 # 重要上下文限制
        self.memory_limit = 1000 # 记忆限制
        
        self.context = []
        self.relationship_type: Optional[str] = None
        self.relationship_score: int = 0
        self.style = None # bot性格风格
        self.important_context = {} # 重要对话
        self.memory = None # 记忆
        self.birth_date = None # 出生日期

    def _reset_sleep_timer(self):
        """重置睡眠定时器"""
        logger.debug(f"Resetting sleep timer for bot {self.bot.id}")
        if self.sleep_task:
            self.sleep_task.cancel()
        self.sleep_task = asyncio.create_task(self._sleep())

    async def _load_bot_context(self) -> None:
        """从数据库加载 bot 上下文"""
        try:
            context_data = await db_manager.get_bot_context(self.bot.id, self.bot.user_id)
            if context_data:
                self.context = context_data.get('context', {})
                self.relationship_type = context_data.get('relationship_type')
                self.relationship_score = context_data.get('relationship_score', 0)
                self.style = getattr(self.bot, f"{self.relationship_type}_style", "")
                self.memory = context_data.get('memory')
                self.important_context = context_data.get('important_context', {})
                logger.info(f"Loaded context for bot {self.bot.id}")
        except Exception as e:
            logger.error(f"Error loading bot context: {str(e)}")

    def _calculate_wait_time(self) -> int:
        """计算等待时间"""
        if not self.context:
            return 0
            
        if self.relationship_type == 'stranger':
            base_time = 100 - self.relationship_score
        elif self.relationship_type in ['friend', 'confidant', 'lover']:
            base_time = 0
        else:
            base_time = 0

        if random.random() < 0.5:  # 50% 概率保持原值
            return base_time
        
        return random.randint(0, base_time)

    async def process_message(self, message: dict) -> None:
        """处理接收到的消息"""
        logger.info(f"Bot {self.bot.id} received message from {message['from_id']}")
        
        self._reset_sleep_timer()
        await self.message_queue.put(message)
        
        # 发送typing状态
        typing_message = {
            'from_id': str(self.bot.id),
            'to_id': message['from_id'],
            'content': '',
            'message_type': 'typing',
            'message_service': message.get('message_service', 'unknown'),
            'timestamp': datetime.now().isoformat()
        }
        await event_bus.publish(EventTypes.SEND_MESSAGE, typing_message)

    async def _process_message_queue(self) -> None:
        """消息队列处理循环"""
        while True:
            try:
                message = await self.message_queue.get()
                combined_content = message['content']
                
                # 等待 process_delay_time，期间如果有新消息则合并内容
                while True:
                    try:
                        await asyncio.sleep(self.process_delay_time)
                        if self.message_queue.empty():
                            break
                        next_message = self.message_queue.get_nowait()
                        combined_content += f"\n{next_message['content']}"
                        message = {**next_message, 'content': combined_content}
                    except asyncio.QueueEmpty:
                        break

                async with self.processing_lock:
                    if not self.is_awake:
                        await self._load_bot_context()
                        self.process_wait_time = self._calculate_wait_time()
                        
                        # 等待 process_wait_time，期间如果有新消息则重新计算等待时间
                        while True:
                            try:
                                await asyncio.sleep(self.process_wait_time)
                                if self.message_queue.empty():
                                    break
                                next_message = self.message_queue.get_nowait()
                                combined_content += f"\n{next_message['content']}"
                                message = {**next_message, 'content': combined_content}
                                self.process_wait_time = self._calculate_wait_time()
                            except asyncio.QueueEmpty:
                                break
                        
                        self.is_awake = True
                        
                    await self._handle_single_message(message)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message queue processing: {str(e)}", exc_info=True)
            finally:
                self.message_queue.task_done()

    async def _handle_single_message(self, message: dict) -> None:
        """
        处理单条消息的核心逻辑
        返回值改为 None，因为消息发送由事件总线处理
        """
        try:
            # 更新上下文
            self.update_context('last_message', message)
            self.update_context('last_message_time', datetime.now())

            # 生成响应
            response_content = await self.generate_response(message)
            if not response_content:
                logger.error("Failed to generate response")
                return

            # 构造响应消息
            response = {
                'from_id': str(self.bot.id),
                'to_id': message['from_id'],
                'content': response_content,  # 直接使用响应内容，不需要 JSON 处理
                'message_type': 'chat',
                'message_service': message.get('message_service', 'unknown'),
                'timestamp': datetime.now().isoformat()
            }

            # 模拟思考和打字时间
            thinking_time = len(str(response_content)) * self.typing_speed
            await asyncio.sleep(thinking_time)

            # 通过事件总线发送响应
            await event_bus.publish(EventTypes.SEND_MESSAGE, response)

            # 保存上下文
            await self.save_context()

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)

    async def generate_response(self, message: dict) -> dict:
        """生成响应消息"""
        try:
            # 构建系统提示
            system_prompt = {
                "role": "system",
                "content": (
                    f"You are Lily, an AI assistant with the following traits:\n"
                    f"Style: {self.style}\n"
                    f"Memory: {self.memory}\n"
                    f"Relationship: {self.relationship_type} (Score: {self.relationship_score})"
                )
            }
            
            # 初始化或更新上下文历史
            if 'history' not in self.context:
                self.context['history'] = [system_prompt]
            elif self.context['history'][0]['role'] != 'system':
                self.context['history'].insert(0, system_prompt)
            
            # 添加用户消息到历史记录
            user_message = {
                "role": "user",
                "content": message['content']
            }
            self.context['history'].append(user_message)
            
            # 准备 LLM API 请求
            llm_request = {
                "messages": self.context['history'][-self.context_limit:],  # 限制上下文长度
            }

            # 调用 LLM API
            llm_response = await self.llm_api.generate_response(llm_request)

            # 验证响应
            if not await self.llm_api.validate_response(llm_response):
                logger.error("Invalid LLM response")
                return None

            # 从响应中提取助手消息
            assistant_message = llm_response['choices'][0]['message']
            
            # 将助手回复添加到历史记录
            self.context['history'].append(assistant_message)
            
            # 管理上下文长度
            if len(self.context['history']) > self.context_limit:
                # 保留系统消息和最近的消息
                self.context['history'] = [
                    self.context['history'][0],  # 系统消息
                    *self.context['history'][-(self.context_limit-1):]  # 最近的消息
                ]

            # 更新重要上下文（如果需要）
            self._update_important_context(message['content'], assistant_message['content'])

            return assistant_message['content']

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return None

    def _update_important_context(self, user_message: str, assistant_response: str) -> None:
        """更新重要上下文"""
        # 简单的重要性判断逻辑
        important_keywords = ['记住', '牢记', '重要', '不要忘记', '记录']
        
        if any(keyword in user_message for keyword in important_keywords):
            timestamp = datetime.now().isoformat()
            self.important_context[timestamp] = {
                'user_message': user_message,
                'assistant_response': assistant_response
            }
            
            # 限制重要上下文的大小
            if len(self.important_context) > self.important_context_limit:
                oldest_key = min(self.important_context.keys())
                del self.important_context[oldest_key]

    async def save_context(self):
        """
        保存上下文到数据库
        """
        try:
            bot_update = {
                'context': self.context,
                'important_context': self.important_context,
                'memory': self.memory
            }
            await db_manager.update_bot(self.bot.id, bot_update)
            
        except Exception as e:
            logger.error(f"Error saving context: {str(e)}")

    async def _sleep(self):
        """睡眠并清理实例"""
        try:
            await asyncio.sleep(self.sleep_timeout)
            await self.before_sleep_task()  # 先执行清理前的准备工作
            
            # 等待清理完成
            if asyncio.iscoroutinefunction(self.cleanup_callback):
                await self.cleanup_callback()
            else:
                self.cleanup_callback()
            
            logger.info(f"Bot {self.bot.id} entered sleep state")
            
        except asyncio.CancelledError:
            logger.debug(f"Sleep task for bot {self.bot.id} cancelled")

    async def before_sleep_task(self):
        """睡眠前的操作"""
        logger.info(f"Starting before-sleep task for bot {self.bot.id}")
        try:
            # 保存当前上下文
            await self.save_context()
            
            # 取消处理任务
            if self.processing_task and not self.processing_task.done():
                logger.info(f"Cancelling processing task for bot {self.bot.id}")
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    pass

            # 清空消息队列 - 修改这部分逻辑
            remaining_messages = []
            while True:
                try:
                    remaining_messages.append(self.message_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            
            # 对收集到的消息执行 task_done
            for _ in remaining_messages:
                self.message_queue.task_done()
            
            # 取消睡眠任务
            if self.sleep_task:
                logger.debug(f"Cancelling sleep task for bot {self.bot.id}")
                self.sleep_task.cancel()
                self.sleep_task = None

            logger.info(f"Before-sleep task completed for bot {self.bot.id}")
        except Exception as e:
            logger.error(f"Error during before-sleep task for bot {self.bot.id}: {str(e)}", exc_info=True)