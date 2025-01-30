import json
import random
import asyncio
import logging
from typing import Any, Dict, Optional, Callable, Awaitable
from .base import BaseModel
from llm_apis import mock_llm as main_llm

from .message_utils import send_message
from .db_utils import load_full_data, update_context, update_memory
from .context_utils import convert_timestamp, varify_context, append_context, remove_last_context, refresh_system_context

logger = logging.getLogger(__name__)

class ModelLily(BaseModel):

    # 导入外部方法
    _convert_timestamp = convert_timestamp
    _send_message = send_message
    _load_full_data = load_full_data
    _update_context = update_context
    _update_memory = update_memory
    _varify_context = varify_context
    _append_context = append_context
    _remove_last_context = remove_last_context
    _refresh_system_context = refresh_system_context

    def __init__(self, bot: Any, message_service: str, cleanup_callback: Callable[[str], Awaitable[None]]):
        """
        初始化 Lily 模型
        Args:
            bot: Bot 实例
            cleanup_callback: 清理回调函数
        """
        # 调用父类的初始化方法
        super().__init__(message_service=message_service, bot=bot, cleanup_callback=cleanup_callback)

        # 特定的初始化
        self.time_zone: str = bot.time_zone # 时区
        self.context: Dict = bot.context # 上下文
        self.memory: str = getattr(bot, 'memory', '') # 记忆
        self.style: str = getattr(bot, f"{bot.relationship_type.value}_style", '') if bot.relationship_type else '' # bot性格风格
        self.relationship_type: Optional[str] = bot.relationship_type.value if bot.relationship_type else None
        self.relationship_score: int = getattr(bot, 'relationship_score', 0)
        self.birth_date: str = getattr(bot, 'birth_date', '') # 出生日期
        self.typing_speed: float = 0     # 打字速度
        # 计算苏醒时间  
        if self.relationship_type == 'stranger':
            self.to_wakeup_time = 2 * (100 - self.relationship_score)
        elif self.relationship_type in ['friend']:
            self.to_wakeup_time = 10
        elif self.relationship_type in ['confidant', 'lover']:
            self.to_wakeup_time = 0
        else:
            self.to_wakeup_time = 0

        self.context_limit: int = 1000 # 上下文限制
        self.memory_limit: int = 1000 # 记忆限制
        self.response_filter: bool = True # 是否过滤响应

        self.to_sleep_time: int = 20      # 睡眠超时时间
        self.to_process_time: int = 4     # 处理消息等待时间
        self.default_system_context: str = "You are Lily, an AI assistant with the following traits:\n"

        # 初始化队列和锁
        self.is_awake = False        # bot是否苏醒
        self.is_processing = False  # 添加处理状态标志
        self.sleep_task: asyncio.Task | None = None       # 睡眠任务
        self.wakeup_task: asyncio.Task | None = None      # 唤醒任务
        self.process_task: asyncio.Task | None = None     # 消息处理任务
        self.message_queue = asyncio.Queue()  # 消息队列

    async def _sleep_timer(self, to_sleep_time: int = 0) -> None:
        """睡眠并清理实例"""
        try:
            logger.debug(f"Starting sleep timer for {to_sleep_time} seconds for bot {self.bot.id}")
            await asyncio.sleep(to_sleep_time)
            
            # 保存当前上下文
            await self._update_context()
            
            # 执行清理回调
            if self.cleanup_callback:
                try:
                    await self.cleanup_callback(str(self.bot.id))
                    logger.debug(f"Cleanup callback executed for bot {self.bot.id}")
                except Exception as e:
                    logger.error(f"Cleanup callback failed for bot {self.bot.id}: {str(e)}", exc_info=True)
                    raise
            
            logger.info(f"Bot {self.bot.id} has entered sleep mode")
            
        except asyncio.CancelledError:
            logger.debug(f"Sleep timer cancelled for bot {self.bot.id}")
            raise
        except Exception as e:
            logger.error(f"Sleep timer failed for bot {self.bot.id}: {str(e)}", exc_info=True)
            raise

    def _set_sleep_timer(self, to_sleep_time: Optional[int] = None) -> None:
        """重置睡眠定时器
        Args:
            to_sleep_time: 睡眠时间, None代表默认值, 0代表取消睡眠定时器
        """
        try:
            logger.debug(f"Resetting sleep timer for bot {self.bot.id}")
            if self.sleep_task and not self.sleep_task.done():
                self.sleep_task.cancel()
                logger.debug(f"Previous sleep timer cancelled for bot {self.bot.id}")
            
            if to_sleep_time == None:
                to_sleep_time = self.to_sleep_time
            
            if to_sleep_time > 0:
                self.sleep_task = asyncio.create_task(self._sleep_timer(to_sleep_time))
                logger.debug(f"New sleep timer set for {to_sleep_time} seconds for bot {self.bot.id}")
        except Exception as e:
            logger.error(f"Failed to set sleep timer for bot {self.bot.id}: {str(e)}", exc_info=True)
            raise

    async def _wakeup_timer(self, to_wakeup_time: int = 0, to_awake: bool = True) -> None:
        """等待时间唤醒
        Args:
            to_wakeup_time: 唤醒时间
            to_awake: 是否唤醒, True代表唤醒, False代表保持睡眠
        """
        try:
            logger.debug(f"Starting wakeup timer for {to_wakeup_time} seconds for bot {self.bot.id}")
            await asyncio.sleep(to_wakeup_time)
            
            if to_awake:
                self.is_awake = True
                logger.info(f"Bot {self.bot.id} has awakened")
            else:
                logger.info(f"Bot {self.bot.id} remains in sleep state")
        except asyncio.CancelledError:
            logger.debug(f"Wakeup timer cancelled for bot {self.bot.id}")
            raise
        except Exception as e:
            logger.error(f"Wakeup timer failed for bot {self.bot.id}: {str(e)}", exc_info=True)
            raise

    async def _wait_wakeup_timer(self, to_wakeup_time: Optional[int] = None) -> None:
        """等待唤醒定时器
        Args:
            to_wakeup_time: 唤醒时间, None代表默认值
        """
        try:
            if self.wakeup_task and not self.wakeup_task.done():
                logger.debug(f"Cancelling existing wakeup timer for bot {self.bot.id}")
                self.wakeup_task.cancel()
                await asyncio.sleep(0)  # 让取消操作完成

            if to_wakeup_time != None:
                logger.debug(f"Setting fixed wakeup timer for {to_wakeup_time} seconds for bot {self.bot.id}")
                self.wakeup_task = asyncio.create_task(asyncio.sleep(to_wakeup_time))
                await self.wakeup_task
                return
            
            if self.is_awake or not self.context or not self.to_wakeup_time:
                logger.debug(f"Bot {self.bot.id} is already awake or context is empty or to_wakeup_time is 0")
                return

            random_number: int = random.randint(1, 100)
            to_wakeup: bool = True

            # 50% 概率保持原值, 50% 概率随机调整
            if random_number <= 50:
                self.to_wakeup_time = int(self.to_wakeup_time * random_number / 50)
                logger.debug(f"Adjusted wakeup time to {self.to_wakeup_time} seconds for bot {self.bot.id}")
            
            # 5% 概率不会唤醒
            if random_number <= 5:
                to_wakeup = False
                logger.debug(f"Bot {self.bot.id} will not wake up (random chance)")

            logger.debug(f"Starting dynamic wakeup timer for {self.to_wakeup_time} seconds for bot {self.bot.id}")
            self.wakeup_task = asyncio.create_task(self._wakeup_timer(self.to_wakeup_time, to_wakeup))
            await self.wakeup_task

        except asyncio.CancelledError:
            logger.debug(f"Wait wakeup timer cancelled for bot {self.bot.id}")
            raise
        except Exception as e:
            logger.error(f"Wait wakeup timer failed for bot {self.bot.id}: {str(e)}", exc_info=True)
            raise

    async def _validate_response(self, response: str|None) -> bool:
        """验证响应"""
        return True

    async def _generate_response(self) -> str|None:
        """生成响应消息"""
        try:
            # 调用 LLM API
            llm_response = await main_llm.generate_response(self.context)

            # 验证响应
            is_valid, error_msg = await main_llm.validate_response(llm_response)
            if not is_valid:
                logger.error(f"Invalid LLM response: {error_msg}")
                raise ValueError(f"LLM response validation failed: {error_msg}")

            # 从响应中提取助手消息
            assistant_message = llm_response['choices'][0]['message']

            return assistant_message['content']

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return None

    async def _process_single_message(self, single_message: str) -> None:
        """处理单个内容"""
        try:
            logger.debug(f"Processing single message: {single_message[:100]}...")
            
            # 更新上下文
            self._varify_context()
            self._append_context("user", single_message)
            logger.debug("Context updated with user message")

            if not self.is_awake:
                logger.info(f"Bot {self.bot.id} is sleeping, skipping message processing")
                # 重置睡眠定时器
                self._set_sleep_timer()
                return

            # 发送typing消息
            asyncio.create_task(self._send_message(message_type='typing'))
            logger.debug("Sent typing indicator")

            response_content = await self._generate_response()
            logger.debug("Generated response from LLM")

            if not await self._validate_response(response_content):
                logger.error("Invalid LLM response")
                return
            
            if not response_content:
                logger.error("Failed to generate response")
                return
            
            self._append_context("assistant", response_content)
            logger.debug("Context updated with assistant response")

            # 打字时间
            typing_time = len(str(response_content)) * self.typing_speed
            logger.debug(f"Starting sleep for {typing_time} seconds...")
            await asyncio.sleep(typing_time)
            logger.debug("Sleep completed")

            # 发送响应消息
            await self._send_message(content=response_content)
            logger.info(f"Sent response message of length {len(response_content)}")

            # 重置睡眠定时器
            self._set_sleep_timer()

            # 保存上下文
            await self._update_context()
            logger.debug("Context saved to database")

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)

    async def _process_message_queue(self) -> None:
        """处理内容队列"""
        self.is_processing = True
        try:
            # 获取队列中的所有消息数量
            queue_size = self.message_queue.qsize()
            if queue_size > 0:
                # 一次性获取并合并所有消息
                single_message = "\n".join([
                    await self.message_queue.get()
                    for _ in range(queue_size)
                ])
                # 处理合并后的消息
                await self._process_single_message(single_message)

        finally:
            self.is_processing = False
            # 如果队列中还有新消息，启动新的处理任务
            if not self.message_queue.empty():
                asyncio.create_task(self._process_message_queue())

    async def _process_timer(self) -> None:
        """消息处理定时器"""
        try:
            # 等待处理消息
            await asyncio.sleep(self.to_process_time)
            # 如果bot未唤醒，等待唤醒
            if not self.is_awake:
                await self._wait_wakeup_timer()
            # 如果当前没有处理过程在运行，启动处理
            if not self.is_processing:
                asyncio.create_task(self._process_message_queue())
        except Exception as e:
            logger.error(f"Error in process timer: {str(e)}", exc_info=True)
            raise

    async def process_message(self, original_message: dict) -> None:
        """
        入口函数，处理接收到的消息
        """
        logger.debug(f"Received message: {original_message}")

        # 取消设置睡眠定时器
        self._set_sleep_timer(0)

        try:
            # 取消现有的消息处理任务
            if self.process_task and not self.process_task.done():
                self.process_task.cancel()
                logger.debug("Cancelled existing process task.")

            # 将消息放入队列
            content = original_message.get('content', '')
            timestamp = original_message.get('timestamp')
            message_type = original_message.get('message_type', '')
            if content and timestamp and message_type == 'chat':
                #formatted_message = f"{content}[{self._convert_timestamp(timestamp)}]"
                #await self.message_queue.put(formatted_message)
                await self.message_queue.put(f"{content}")
                logger.debug("Message appended to the message queue.")
            else:
                logger.warning("Skipping message due to missing content timestamp or message type.")

            # 创建新的消息处理任务
            self.process_task = asyncio.create_task(self._process_timer())
            logger.debug("New process task created.")

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)