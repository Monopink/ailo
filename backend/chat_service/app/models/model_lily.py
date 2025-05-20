import json
import random
import asyncio
import logging
from typing import Any, Dict, Optional, Callable, Awaitable

from .base import BaseModel
from llm_apis import model_lily_llm as llm
from enums import MessageType, MessageTypeCategory
from db_managers import db_manager
from .message_parts import convert_timestamp, send_message
from .db_parts import load_full_data, update_context, update_memory
from .context_parts import (
    varify_context,
    append_context,
    remove_last_context,
    refresh_system_context,
    create_instant_context,
)

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
    _create_instant_context = create_instant_context

    def __init__(
        self,
        bot: Any,
        message_service: str,
        cleanup_callback: Callable[[str], Awaitable[None]],
    ):
        """初始化 Lily 模型
        Args:
            bot: Bot 实例
            cleanup_callback: 清理回调函数
        """
        # 调用父类的初始化方法
        super().__init__(
            message_service=message_service, bot=bot, cleanup_callback=cleanup_callback
        )

        # 初始化会变化bot的数据
        self.context: Dict = getattr(bot, "context", {})  # 上下文
        self.memory: str = getattr(bot, "memory", "")  # 记忆

        # 新的关系系统
        self.friend_score: int = getattr(bot, "friend_score", 0)
        self.romance_score: int = getattr(bot, "romance_score", 0)

        # 直接使用数据库字段，不构建字典
        self.relationship_type: str = getattr(bot, "relationship_type", "friend")
        self.relationship_level: str = getattr(bot, "relationship_level", "neutral")
        self.relationship_style: str = getattr(bot, "relationship_style", "")

        # 其他配置
        self.friend_config: list = getattr(bot, "friend_config", [])
        self.romance_config: list = getattr(bot, "romance_config", [])
        self.override_config: Dict = getattr(bot, "override_config", {})
        self.is_polite: bool = bool(getattr(bot, "is_polite", 0))
        self.is_crushing: bool = bool(getattr(bot, "is_crushing", 0))
        self.emotions_config: Dict = getattr(bot, "emotions_config", {})

        # 分数相关字段
        self.friend_score_pos_k: int = getattr(bot, "friend_score_pos_k", 1000)
        self.friend_score_neg_k: int = getattr(bot, "friend_score_neg_k", 100)
        self.romance_score_k: int = getattr(bot, "romance_score_k", 1000)
        self.friend_score_upper_limit: int = getattr(
            bot, "friend_score_upper_limit", 5000
        )
        self.friend_score_lower_limit: int = getattr(bot, "friend_score_lower_limit", 0)
        self.romance_score_upper_limit: int = getattr(
            bot, "romance_score_upper_limit", 5000
        )
        self.friend_score_anger_minus: int = getattr(bot, "friend_score_anger_minus", 0)
        self.romance_score_anger_minus: int = getattr(
            bot, "romance_score_anger_minus", 0
        )

        self.instant_context: str = ""  # 即时上下文
        self.message_tag: str = " [msg] "  # 消息分隔符

        # 初始化其他数据
        self.typing_speed: float = 0  # 打字速度
        self.to_wakeup_secs: int = 0  # 当前苏醒时间
        self.default_to_wakeup_secs: int  # 默认苏醒时间

        # 根据关系类型和等级设置默认苏醒时间
        relation_type = self.relationship_type
        relation_level = self.relationship_level

        if relation_type == "friend":
            if relation_level in ["hostile", "cold"]:
                self.default_to_wakeup_secs = 60
            elif relation_level == "neutral":
                self.default_to_wakeup_secs = 30
            elif relation_level == "friendly":
                self.default_to_wakeup_secs = 15
            elif relation_level == "warm":
                self.default_to_wakeup_secs = 5
            else:
                self.default_to_wakeup_secs = 30
        elif relation_type == "romance":
            if relation_level == "intimate":
                self.default_to_wakeup_secs = 3
            elif relation_level == "romantic":
                self.default_to_wakeup_secs = 0
            else:
                self.default_to_wakeup_secs = 10
        else:
            self.default_to_wakeup_secs = 30

        self.context_limit: int = 1000  # 上下文限制
        self.memory_limit: int = 1000  # 记忆限制
        self.need_summary: bool = False  # 是否需要总结
        self.response_filter: bool = True  # 是否过滤响应

        self.to_sleep_secs: int = 120  # 睡眠超时时间
        self.chat_secs: int = 2  # 处理chat消息等待时间
        self.typing_secs_total: int = 32  # typing消息总等待时间
        self.typing_secs_short: int = 16  # 收到typing消息等待时间
        self.typing_end_secs: int = self.chat_secs  # 收到typing_end消息等待时间
        self.chat_notyping_secs: int = 8  # 处理chat_notyping消息等待时间

        # 初始化队列和锁
        self.is_awake: bool = False  # bot是否苏醒
        self.is_processing: bool = False  # 添加处理状态标志
        self.sleep_task: asyncio.Task | None = None  # 睡眠任务
        self.wakeup_task: asyncio.Task | None = None  # 唤醒任务
        self.process_task_main: asyncio.Task | None = None  # 主消息处理任务
        self.process_task_sub: asyncio.Task | None = None  # 快消息处理任务
        self.combined_message: str = ""  # 合并的消息
        self.combining_lock: asyncio.Lock = asyncio.Lock()  # 合并锁
        self.last_message_type: Optional[MessageType] = None
        self.include_timestamp: bool = True  # 是否记录消息时间戳

    async def _sleep_timer(self, to_sleep_secs: int = 0) -> None:
        """睡眠并清理实例"""
        try:
            logger.debug(
                f"Starting sleep timer for {to_sleep_secs} seconds for bot {self.bot.id}"
            )
            await asyncio.sleep(to_sleep_secs)

            # 保存当前上下文
            await self._update_context()

            # 执行清理回调
            if self.cleanup_callback:
                try:
                    await self.cleanup_callback(str(self.bot.entity_id))
                    logger.debug(f"Cleanup callback executed for bot {self.bot.id}")
                except Exception as e:
                    logger.error(
                        f"Cleanup callback failed for bot {self.bot.id}: {str(e)}",
                        exc_info=True,
                    )
                    raise

            logger.info(f"Bot {self.bot.id} has entered sleep mode")

        except asyncio.CancelledError:
            logger.debug(f"Sleep timer cancelled for bot {self.bot.id}")
            raise
        except Exception as e:
            logger.error(
                f"Sleep timer failed for bot {self.bot.id}: {str(e)}", exc_info=True
            )
            raise

    def _reset_sleep_timer(self, to_sleep_secs: Optional[int] = None) -> None:
        """重置睡眠定时器
        Args:
            to_sleep_secs: 睡眠时间, None代表默认值, 0代表取消睡眠定时器
        """
        logger.debug(f"Resetting sleep timer for bot {self.bot.id}")
        if self.sleep_task and not self.sleep_task.done():
            self.sleep_task.cancel()
            logger.debug(f"Previous sleep timer cancelled for bot {self.bot.id}")

        if to_sleep_secs is None:
            to_sleep_secs = self.to_sleep_secs

        if to_sleep_secs > 0:
            self.sleep_task = asyncio.create_task(self._sleep_timer(to_sleep_secs))
            logger.debug(
                f"New sleep timer set for {to_sleep_secs} seconds for bot {self.bot.id}"
            )

    async def _wakeup_timer(self, to_awake: bool = True) -> None:
        """等待时间唤醒
        Args:
            to_awake: 是否唤醒, True代表唤醒, False代表保持睡眠
        """
        logger.debug(
            f"To wakeup timer is {self.to_wakeup_secs} seconds for bot {self.bot.id}"
        )
        while self.to_wakeup_secs > 0:
            await asyncio.sleep(1)
            self.to_wakeup_secs -= 1

        logger.debug(f"To wakeup timer is over for bot {self.bot.id}")
        if to_awake:
            self.is_awake = True
            logger.info(f"Bot {self.bot.id} has woken up")
            return
        else:
            self.is_awake = False
            logger.info(f"Bot {self.bot.id} has entered sleep mode")
            return

    async def _wait_wakeup_timer(self, to_wakeup_secs: Optional[int] = None) -> None:
        """等待唤醒定时器
        Args:
            to_wakeup_secs: 唤醒时间, None代表默认值
        """
        if self.is_awake:
            logger.debug("Bot is awake, skipping wakeup timer")
            return
        if not self.context:
            self.to_wakeup_secs = 0
            logger.debug("Bot is not awake, setting to wakeup timer to 0")
            await self._wakeup_timer()
            return

        if self.wakeup_task and not self.wakeup_task.done():
            self.wakeup_task.cancel()
            await asyncio.sleep(0)
            logger.debug("Cancelled existing wakeup timer.")

        if to_wakeup_secs is not None:
            self.to_wakeup_secs = to_wakeup_secs
            logger.debug(
                f"Setting fixed wakeup timer for {to_wakeup_secs} seconds for bot {self.bot.id}"
            )
            self.wakeup_task = asyncio.create_task(self._wakeup_timer())
            logger.debug("Created new wakeup timer")
            await self.wakeup_task
            return

        else:
            if not self.to_wakeup_secs:
                self.to_wakeup_secs = self.default_to_wakeup_secs

            random_number: int = random.randint(1, 100)
            to_wakeup: bool = True

            # 50% 概率保持原值, 50% 概率随机调整
            if random_number <= 50:
                self.to_wakeup_secs = max(
                    int(self.to_wakeup_secs * random_number / 50), 1
                )

            # 5% 概率不会唤醒
            if random_number <= 5:
                to_wakeup = False

            self.wakeup_task = asyncio.create_task(self._wakeup_timer(to_wakeup))
            logger.debug("Created new wakeup timer")
            await self.wakeup_task

    async def _validate_response(self, response: str | None) -> bool:
        """验证响应

        根据 context_strategy 提供的格式验证响应是否符合要求

        Args:
            response: LLM 生成的响应字符串

        Returns:
            bool: 验证是否通过
        """
        if not response:
            logger.error("Response is empty")
            return False

        try:
            # 解析 JSON 响应
            response_data = json.loads(response)

            # 必需字段检查
            required_fields = [
                "is_attack",
                "response",
                "content",
                "emotions",
                "friend_score",
                "romance_score",
            ]

            for field in required_fields:
                if field not in response_data:
                    logger.error(f"Missing required field: {field}")
                    return False

            # 类型检查
            if not isinstance(response_data["is_attack"], bool):
                logger.error("Field 'is_attack' must be a boolean")
                return False

            if not isinstance(response_data["response"], bool):
                logger.error("Field 'response' must be a boolean")
                return False

            if not isinstance(response_data["content"], str):
                logger.error("Field 'content' must be a string")
                return False

            # 检查情绪字段
            emotions = response_data["emotions"]
            if not isinstance(emotions, dict):
                logger.error("Field 'emotions' must be a dictionary")
                return False

            if "types" not in emotions or "scores" not in emotions:
                logger.error("Field 'emotions' must contain 'types' and 'scores'")
                return False

            if not isinstance(emotions["types"], list):
                logger.error("Field 'emotions.types' must be a list")
                return False

            if not isinstance(emotions["scores"], dict):
                logger.error("Field 'emotions.scores' must be a dictionary")
                return False

            # 检查分数字段
            if not isinstance(response_data["friend_score"], int):
                logger.error("Field 'friend_score' must be an integer")
                return False

            if not isinstance(response_data["romance_score"], int):
                logger.error("Field 'romance_score' must be an integer")
                return False

            # 检查分数范围
            if not (-5 <= response_data["friend_score"] <= 5):
                logger.error("Field 'friend_score' must be between -5 and 5")
                return False

            if not (-5 <= response_data["romance_score"] <= 5):
                logger.error("Field 'romance_score' must be between -5 and 5")
                return False

            # 如果有总结字段，检查类型
            if "summary" in response_data and not isinstance(
                response_data["summary"], str
            ):
                logger.error("Field 'summary' must be a string")
                return False

            return True

        except json.JSONDecodeError:
            logger.error("Response is not valid JSON")
            return False
        except Exception as e:
            logger.error(f"Error validating response: {str(e)}")
            return False

    async def _generate_response(self) -> str | None:
        """生成响应"""
        try:
            # 调用 LLM API
            llm_response = await llm.generate_response(self.context)

            # 验证响应
            is_valid, error_msg = await llm.validate_response(llm_response)
            if not is_valid:
                logger.error(f"Invalid LLM response: {error_msg}")
                raise ValueError(f"LLM response validation failed: {error_msg}")

            # 从响应中提取助手消息
            assistant_message = llm_response["choices"][0]["message"]
            response_content = assistant_message["content"]

            # 处理情绪和关系分数
            await self._process_emotions_and_scores(response_content)

            return response_content

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)
            return None

    async def _process_emotions_and_scores(self, response_content: str) -> None:
        """处理情绪和关系分数"""
        try:
            # 解析 JSON 响应
            response_data = json.loads(response_content)

            # 处理情绪分数
            if "emotions" in response_data:
                emotions_data = response_data["emotions"]
                emotion_types = emotions_data.get("types", [])
                emotion_scores = emotions_data.get("scores", {})

                # 更新情绪数据库
                for emotion_type in emotion_types:
                    if emotion_type in emotion_scores:
                        emotion_score = emotion_scores[emotion_type]
                        # 根据分数确定等级
                        emotion_level = 0
                        if emotion_type in self.emotions_config:
                            thresholds = self.emotions_config.get(emotion_type, [])
                            for threshold_config in thresholds:
                                if emotion_score >= threshold_config.get(
                                    "threshold", 0
                                ):
                                    emotion_level = threshold_config.get("level", 0)

                        # 更新数据库
                        await db_manager.update_bot_emotion(
                            self.bot.id, emotion_type, emotion_score, emotion_level
                        )
                        logger.debug(
                            f"Updated emotion {emotion_type} with score {emotion_score} and level {emotion_level}"
                        )

            # 处理友情分数
            friend_score = response_data.get("friend_score", 0)
            # 处理浪漫分数
            romance_score = response_data.get("romance_score", 0)

            # 更新关系分数
            if friend_score != 0 or romance_score != 0:
                # 计算实际增减的分数
                friend_delta = (
                    friend_score * self.friend_score_pos_k
                    if friend_score > 0
                    else friend_score * self.friend_score_neg_k
                )
                romance_delta = romance_score * self.romance_score_k

                # 应用情绪影响
                # 如果有生气情绪，减少分数增长
                if (
                    hasattr(self, "friend_score_anger_minus")
                    and self.friend_score_anger_minus > 0
                ):
                    if friend_delta > 0:
                        friend_delta = max(
                            0, friend_delta - self.friend_score_anger_minus
                        )

                if (
                    hasattr(self, "romance_score_anger_minus")
                    and self.romance_score_anger_minus > 0
                ):
                    if romance_delta > 0:
                        romance_delta = max(
                            0, romance_delta - self.romance_score_anger_minus
                        )

                # 更新分数
                new_friend_score = max(
                    self.friend_score_lower_limit,
                    min(
                        self.friend_score_upper_limit,
                        self.friend_score + friend_delta,
                    ),
                )
                new_romance_score = max(
                    0,
                    min(
                        self.romance_score_upper_limit,
                        self.romance_score + romance_delta,
                    ),
                )

                # 更新数据库
                await db_manager.update_bot(
                    self.bot.id,
                    {
                        "friend_score": new_friend_score,
                        "romance_score": new_romance_score,
                    },
                )

                # 更新本地值
                self.friend_score = new_friend_score
                self.romance_score = new_romance_score

                logger.debug(
                    f"Updated relationship scores: friend_score={new_friend_score}, romance_score={new_romance_score}"
                )

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing response JSON: {str(e)}")
        except Exception as e:
            logger.error(
                f"Error processing emotions and scores: {str(e)}", exc_info=True
            )

    async def _reply_message(self, response_content: str) -> None:
        """回复消息"""
        try:
            # 打字时间
            typing_secs = len(str(response_content)) * self.typing_speed
            logger.debug(f"Starting typing for {typing_secs} seconds...")
            await asyncio.sleep(typing_secs)
            logger.debug("Typing completed")

            # 发送响应消息
            await self._send_message(content=response_content)
            logger.info(f"Sent response message of length {len(response_content)}")

            # 重置睡眠定时器
            self._reset_sleep_timer()

            # 保存上下文
            await self._update_context()
            logger.debug("Context saved to database")

        except Exception as e:
            logger.error(f"Error replying message: {str(e)}", exc_info=True)

    async def _process_message(self) -> None:
        """处理消息"""
        self.is_processing = True
        try:
            logger.debug("Processing message...")

            # 更新上下文
            self._varify_context()
            async with self.combining_lock:
                self._append_context("user", self.combined_message)
                self.combined_message = ""
            logger.debug("Context updated with user message")

            # 如果bot未唤醒，不响应
            if not self.is_awake:
                logger.info(f"Bot {self.bot.id} is sleeping, skipping message response")
                # 重置睡眠定时器
                self._reset_sleep_timer()
                return

            # 发送typing消息
            asyncio.create_task(
                self._send_message(message_type=MessageType.TYPING.name)
            )
            logger.debug("Sent typing indicator")

            try:
                # 刷新系统上下文
                self._refresh_system_context()
            except Exception as e:
                logger.error(f"Failed to refresh system context: {str(e)}")
                return  # 如果刷新系统上下文失败，直接返回

            try:
                # 生成响应
                response_content = await self._generate_response()
                logger.debug("Generated response from LLM")
            except Exception as e:
                logger.error(f"Failed to generate response: {str(e)}")
                return  # 如果生成响应失败，直接返回

            # 验证响应
            if not await self._validate_response(response_content):
                logger.error("Invalid LLM response")
                return

            if not response_content:
                logger.error("Failed to generate response")
                return

            content_value = json.loads(response_content).get("content", "")
            saveable_content = f"[{self._convert_timestamp()}]\n{content_value}"
            self._append_context("assistant", saveable_content)
            logger.debug("Context updated with assistant response")

            # 回复消息
            asyncio.create_task(self._reply_message(response_content))

            self.last_message_type = None

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            raise

        finally:
            self.is_processing = False
            # 如果队列中还有新消息，启动新的处理任务
            if self.combined_message != "":
                logger.debug(f"combined_message: {self.combined_message}")
                asyncio.create_task(self._process_message())

    async def _process_timer(self, to_process_secs: int) -> None:
        """消息处理定时器"""
        try:
            # 处理消息等待
            await asyncio.sleep(to_process_secs)
            self.include_timestamp = True
            # 如果bot未唤醒，等待唤醒
            if not self.is_awake:
                await self._wait_wakeup_timer()
            # 如果当前没有处理过程在运行，启动处理
            if not self.is_processing and self.combined_message != "":
                asyncio.create_task(self._process_message())
            # 结束其他定时器
            self._reset_process_timer(0, 0)
        except Exception as e:
            logger.error(f"Error in process timer: {str(e)}", exc_info=True)
            raise

    def _reset_process_timer(
        self,
        secs_main: int | None = None,
        secs_sub: int | None = None,
        secs_adjust: int | None = None,
    ) -> None:
        """重置消息处理定时器
        Args:
            secs_main: 主消息处理时间, None代表不操作，0代表取消，其他代表设置
            secs_sub: 子消息处理时间, None代表不操作，0代表取消，其他代表设置
            secs_adjust: 调整主消息处理时间, None代表不操作，0代表取消，其他代表设置
        """
        # 取消现有的子消息处理任务
        if (
            secs_sub is not None
            and self.process_task_sub
            and not self.process_task_sub.done()
        ):
            self.process_task_sub.cancel()
            logger.debug("Cancelled existing process_task_sub.")
        # 取消现有的主消息处理任务
        if (
            (secs_main is not None or secs_adjust is not None)
            and self.process_task_main
            and not self.process_task_main.done()
        ):
            self.process_task_main.cancel()
            logger.debug("Cancelled existing process_task_main.")
            if secs_adjust is not None:
                secs_main = secs_adjust
        # 创建新的主消息处理任务
        if secs_main:
            self.process_task_main = asyncio.create_task(self._process_timer(secs_main))
            logger.debug(f"New process_task_main created. secs: {secs_main}")
        # 创建新的子消息处理任务
        if secs_sub and self.process_task_main:
            self.process_task_sub = asyncio.create_task(self._process_timer(secs_sub))
            logger.debug(f"New process_task_sub created. secs: {secs_sub}")

    async def receive_message(self, received_message: dict) -> None:
        """入口函数，接收消息"""
        logger.debug(f"Received message: {received_message}")

        try:
            content = received_message.get("content", "")
            timestamp = received_message.get("timestamp")
            message_type = MessageType.parse(received_message.get("message_type", ""))

            if not timestamp:
                logger.warning(
                    "Skipping process message due to missing content or timestamp."
                )
            elif not message_type:
                logger.warning("Skipping process message due to missing message_type.")

            # 处理chat\chat_notyping消息
            elif content and message_type.category == MessageTypeCategory.CONTENT:
                # 取消设置睡眠定时器
                self._reset_sleep_timer(0)

                # 取消现有的消息处理任务
                self._reset_process_timer(0, 0)

                # 将消息合并
                async with self.combining_lock:
                    if self.include_timestamp is True:
                        self.combined_message += (
                            f"[{self._convert_timestamp(timestamp)}]\n"
                        )
                        self.include_timestamp = False
                    self.combined_message += self.message_tag + f"{content}"
                logger.debug("Message appended to the message queue.")

                # 创建新的消息处理任务
                if message_type == MessageType.CHAT:
                    self._reset_process_timer(self.chat_secs)
                else:
                    self._reset_process_timer(self.chat_notyping_secs)

            elif not self.last_message_type:
                logger.warning(
                    "Skipping process message due to missing last_message_type."
                )

            # 处理typing_end消息
            elif (
                self.last_message_type == MessageType.TYPING
                and message_type == MessageType.TYPING_END
            ):
                self._reset_process_timer(None, self.typing_end_secs)

            # 处理上一条消息是chat消息，当前消息是typing消息
            elif (
                self.last_message_type == MessageType.CHAT
                and message_type == MessageType.TYPING
            ):
                self._reset_process_timer(
                    None,
                    self.typing_secs_short,
                    self.typing_secs_total,
                )
            # 如果上一条消息是typing_end消息, 当前消息是typing消息
            elif (
                self.last_message_type == MessageType.TYPING_END
                and message_type == MessageType.TYPING
            ):
                self._reset_process_timer(
                    None,
                    self.typing_secs_short,
                )

            # 记录上一条消息类型
            self.last_message_type = message_type

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
