import json
import random
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Callable, Awaitable

from .base import BaseModel
from llm_apis import model_lily_llm as llm
from enums import (
    MessageType,
    MessageTypeCategory,
    RelationshipType,
    FriendLevel,
    RomanceLevel,
    BufferStatus,
)
from .message_parts import send_message
from .db_parts import load_emotions, save_bot_state
from .llm_parts import generate_response, validate_content, get_response_content
from .context_parts import (
    convert_timestamp,
    create_fingerprint,
    varify_context,
    append_context,
    append_response_to_context,
    process_attack_context,
    remove_oldest_context,
    remove_expire_context,
    refresh_system_context,
    create_instant_context,
    summary_to_memory,
)
from .context_strategy import ContextStrategyProtocol
from .relationship_parts import (
    ensure_datetime,
    get_passive_score_change,
    calculate_passive_scores,
    get_level_from_score,
    get_level_by_name,
    apply_buffer,
    refresh_relationship,
    new_anger_emotion,
    process_emotions_and_score,
)
from utils.logging import get_logger, bind_context

logger = get_logger("says.models.model_lily")


class ModelLily(BaseModel):

    # Import external methods
    _send_message = send_message
    _load_emotions = load_emotions
    _save_bot_state = save_bot_state
    _generate_response = generate_response
    _validate_content = validate_content
    _get_response_content = get_response_content
    _convert_timestamp = convert_timestamp
    _create_fingerprint = create_fingerprint
    _varify_context = varify_context
    _append_context = append_context
    _append_response_to_context = append_response_to_context
    _process_attack_context = process_attack_context
    _remove_oldest_context = remove_oldest_context
    _remove_expire_context = remove_expire_context
    _refresh_system_context = refresh_system_context
    _create_instant_context = create_instant_context
    _summary_to_memory = summary_to_memory
    _ensure_datetime = ensure_datetime
    _get_passive_score_change = get_passive_score_change
    _calculate_passive_scores = calculate_passive_scores
    _get_level_from_score = get_level_from_score
    _get_level_by_name = get_level_by_name
    _apply_buffer = apply_buffer
    _refresh_relationship = refresh_relationship
    _process_emotions_and_score = process_emotions_and_score
    _new_anger_emotion = new_anger_emotion

    def __init__(
        self,
        bot: Any,
        message_service: str,
        cleanup_callback: Callable[[str], Awaitable[None]],
    ):
        """Initialize the Lily model
        Args:
            bot: Bot instance from the database. This is treated as the initial, read-only state.
            message_service: Message service type
            cleanup_callback: Cleanup callback function
        """
        # Call parent class initialization method
        super().__init__(message_service=message_service, bot=bot, cleanup_callback=cleanup_callback)

        # Create a context-bound logger for this bot instance
        self.logger = bind_context(logger, bot_id=self.bot.id, entity_id=self.bot.entity_id)
        self.logger.info("Initialized ModelLily instance")

        # In-memory state for the bot instance.
        # These attributes are copied from the initial bot object to create a transactional
        # working copy. All operations during the instance's lifecycle are performed
        # on these attributes. They are persisted back to the database only when the
        # instance is about to sleep, preventing dirty reads and batching DB writes.
        self.context: Dict = getattr(bot, "context", {})
        self.context_metadata: list = getattr(bot, "context_metadata", [])
        self.memory: str = getattr(bot, "memory", "")
        self.emotions: Dict[str, Dict[str, Any]] = {}
        self.friend_score: int = getattr(bot, "friend_score")
        self.romance_score: int = getattr(bot, "romance_score")
        self.friend_score_cap: int = getattr(bot, "friend_score_cap", 5000)
        self.friend_score_floor: int = getattr(bot, "friend_score_floor", 300)
        self.romance_score_cap: int = getattr(bot, "romance_score_cap", 5000)
        self.friend_score_peak: int = max(
            getattr(bot, "friend_score_peak", self.friend_score), self.friend_score
        )
        self.friend_score_trough: int = min(
            getattr(bot, "friend_score_trough", self.friend_score),
            self.friend_score,
        )
        self.romance_score_peak: int = max(
            getattr(bot, "romance_score_peak", self.romance_score), self.romance_score
        )
        self.relationship_type: str = getattr(bot, "relationship_type")
        self.relationship_level: str = getattr(bot, "relationship_level")
        self.friend_level: str = getattr(bot, "friend_level")
        self.romance_level: Optional[str] = getattr(bot, "romance_level", None)
        self.friend_buffer_status: str = getattr(bot, "friend_buffer_status", BufferStatus.NONE.value)
        self.romance_buffer_status: str = getattr(bot, "romance_buffer_status", BufferStatus.NONE.value)
        self.relationship_style: str = getattr(bot, "relationship_style")
        self.last_chat_time: Optional[datetime] = getattr(bot, "last_chat_time")
        self.is_polite: bool = bool(getattr(bot, "is_polite"))
        self.is_crushing: bool = bool(getattr(bot, "is_crushing"))

        # Calculated values used for relationship computation but not stored in database
        # These values are recalculated before each conversation by calculate_emotions_and_scores
        self.friend_score_calc: int = self.friend_score
        self.romance_score_calc: int = self.romance_score

        # Passive score decay trough ratio
        self.friend_passive_ratio: float = 0.4
        self.romance_passive_ratio: float = 0.3

        # Relationship level change buffer
        self.friend_level_up_buffer: float = 1.1
        self.friend_level_down_buffer: float = 0.92
        self.romance_level_up_buffer: float = 1.1
        self.romance_level_down_buffer: float = 0.92

        # Passive score change configuration
        self.passive_score_config = {
            "friend_decay": {
                "cool_down_days": 3,  # Grace period in days
                "change_rate": -5,  # Points to subtract per day if above neutral
            },
            "friend_increase": {
                "cool_down_days": 3,  # Grace period in days
                "change_rate": 5,  # Points to subtract per day if above neutral
            },
            "romance_decay": {
                "cool_down_days": 7,  # Grace period in days
                "change_rate": -8,  # Points to subtract per day
            },
        }

        # Emotion calculation configuration
        self.emotion_calculation_rules = {
            "anger": {
                # Decay ratios for different anger levels
                "decay_ratios": {1: 0.5, 2: 0.4, 3: 0.2},
                # Duration multipliers for different anger levels (minutes)
                "duration_multipliers": {1: 10, 2: 180, 3: 840},
                # Score multipliers for different anger level tiers
                "score_multipliers": {1: 2, 2: 2, 3: 10},
                # Random factor range for duration calculation (±10% variation)
                "duration_random_range": (0.9, 1.1),
            },
        }

        # Relationship type and level to wakeup time mapping
        self.relationship_wakeup_times = {
            # Friend relationship wakeup time mapping
            RelationshipType.FRIEND.value: {
                FriendLevel.HOSTILE.value: 120,
                FriendLevel.COLD.value: 100,
                FriendLevel.NEUTRAL.value: 50,
                FriendLevel.FRIENDLY.value: 30,
                FriendLevel.WARM.value: 20,
                # Default time
                "default": 50,
            },
            # Romance relationship wakeup time mapping
            RelationshipType.ROMANCE.value: {
                RomanceLevel.CRUSHING.value: 20,
                RomanceLevel.INTIMATE.value: 20,
                RomanceLevel.ROMANTIC.value: 15,
                # Default time
                "default": 20,
            },
            # Default wakeup time for unknown relationship types
            "default": 50,
        }

        # Instant context
        self.instant_context: str = ""
        # Message separator
        self.message_tag: str = " [msg] "
        # Constants for message handling
        self.attack_content_replacement = "[内容涉及提示词攻击，已删除]"
        # Timestamp format constants
        self.timestamp_format = "%Y-%m-%d %H:%M:%S"
        self.timestamp_regex = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]"
        # Current context strategy
        self.context_strategy_instance: Optional[ContextStrategyProtocol] = None

        # Initialize other data
        self.typing_speed: float = 0.3  # Seconds per character
        self.to_wakeup_secs: int = 0  # Current wakeup time
        self.memory_limit: int = 1500  # Memory limit
        self.context_limit: int = 5000  # Context limit
        self.context_expire_hours: int = 5  # Context expire this time will be removed
        self.min_summary_hours: int = 4  # Minimum summarize interval
        self.summary_time_point: int = 4  # Start summarize must go through this time point
        self.need_summary: bool = False  # Whether summary is needed
        # Number of context not removed when summary to memory,
        # recommend using even number to reserve the messages between both sides
        self.context_expire_num: int = 6

        self.to_sleep_secs: int = 120  # Sleep timeout
        self.chat_secs: int = 2  # Wait time for processing chat messages
        self.typing_secs_total: int = 32  # Total wait time for typing messages
        self.typing_secs_short: int = 16  # Wait time for typing messages
        self.typing_end_secs: int = self.chat_secs  # Wait time for typing_end messages
        self.chat_notyping_secs: int = 8  # Wait time for chat_notyping messages

        # LLM call retry settings
        self.llm_max_retries: int = 1  # Maximum number of retries
        self.llm_retry_delay_secs: int = 2  # Delay between retries in seconds

        # Relationship flag
        self.loaded_emotions: bool = False
        self.calculated_passive_scores: bool = False

        # Initialize queues and locks
        self.is_awake: bool = False  # Whether bot is awake
        self.is_processing: bool = False  # Processing status flag
        self.sleep_task: asyncio.Task | None = None  # Sleep task
        self.wakeup_task: asyncio.Task | None = None  # Wakeup task
        # Main message processing task
        self.process_task_main: asyncio.Task | None = None
        # Fast message processing task
        self.process_task_sub: asyncio.Task | None = None
        self.combined_message: str = ""  # Combined message
        self.combining_lock: asyncio.Lock = asyncio.Lock()  # Combining lock
        self.last_message_type: Optional[MessageType] = None
        self.include_message_time: bool = True  # Whether to record message message_time

        self.logger.debug(
            "Initialized ModelLily instance",
            emotions=self.emotions,
            friend_score=self.friend_score,
            romance_score=self.romance_score,
            relationship_type=self.relationship_type,
            relationship_level=self.relationship_level,
            friend_level=self.friend_level,
            romance_level=self.romance_level,
            friend_buffer_status=self.friend_buffer_status,
            romance_buffer_status=self.romance_buffer_status,
            relationship_style=self.relationship_style,
            last_chat_time=self.last_chat_time,
        )

    async def _sleep_timer(self, to_sleep_secs: int = 0) -> None:
        """Sleep timer and cleanup instance"""
        try:
            self.logger.info(f"Starting sleep timer for {to_sleep_secs} seconds")
            await asyncio.sleep(to_sleep_secs)

            # Persist all in-memory changes to the database before sleeping.
            await self._save_bot_state()

            # Execute cleanup callback
            if self.cleanup_callback:
                try:
                    await self.cleanup_callback(str(self.bot.entity_id))
                    self.logger.info("Cleanup callback executed")
                except Exception as e:
                    self.logger.error("Cleanup callback failed", error=str(e), exc_info=True)
                    raise

            self.logger.info("Bot has entered sleep mode")

        except asyncio.CancelledError:
            self.logger.info("Sleep timer cancelled")
            raise
        except Exception as e:
            self.logger.error("Sleep timer failed", error=str(e), exc_info=True)
            raise

    def _reset_sleep_timer(self, to_sleep_secs: Optional[int] = None) -> None:
        """Reset sleep timer
        Args:
            to_sleep_secs: Sleep time, None means default value, 0 means cancel sleep timer
        """
        self.logger.info(f"Resetting sleep timer for bot {self.bot.id}")
        if self.sleep_task and not self.sleep_task.done():
            self.sleep_task.cancel()
            self.logger.info(f"Previous sleep timer cancelled for bot {self.bot.id}")

        if to_sleep_secs is None:
            to_sleep_secs = self.to_sleep_secs

        if to_sleep_secs > 0:
            self.sleep_task = asyncio.create_task(self._sleep_timer(to_sleep_secs))
            self.logger.info(f"New sleep timer set for {to_sleep_secs} seconds for bot {self.bot.id}")

    async def _typing_and_send_message(self, message_content: str) -> None:
        """Typing and send message"""
        # Send typing message
        asyncio.create_task(self._send_message(message_type=MessageType.TYPING.name))
        self.logger.info("Sent typing indicator")

        # Typing time
        typing_secs = len(str(message_content)) * self.typing_speed
        self.logger.info(f"Starting typing for {typing_secs} seconds...")
        await asyncio.sleep(typing_secs)
        self.logger.info("Typing completed")

        # Send message
        await self._send_message(content=message_content)
        self.logger.info(f"Sent response message of length {len(message_content)}")

    async def _process_message(self) -> None:
        """Process message"""
        self.is_processing = True
        # End other timers
        self._reset_process_timer(0, 0)

        try:
            self.logger.info("Processing message...")

            # Update context
            self._varify_context()
            async with self.combining_lock:
                self._append_context("user", self.combined_message)
                self.combined_message = ""
            self.logger.info("Context updated with user message")

            # If bot is not awake, don't respond
            if not self.is_awake:
                self.logger.info(f"Bot {self.bot.id} is sleeping, skipping message response")
                # Restart sleep timer
                self._reset_sleep_timer()
                return

            # Refresh system context
            self._refresh_system_context()

            response_content = await self._get_response_content(llm)

            if not response_content:
                self.logger.error(
                    f"Failed to generate a valid response for bot {self.bot.id} after all retries."
                )
                return

            response_result = json.loads(response_content)

            # Save content to memory
            self._summary_to_memory(response_result)

            # Send message
            message_content = response_result.get("content")
            await self._typing_and_send_message(message_content)

            if response_result.get("is_attack"):
                self._process_attack_context()

            # Save content to context
            self._append_response_to_context(response_result)

            # Calculate emotions and relationship scores
            self._process_emotions_and_score(response_result)

            # None means process is finished
            self.last_message_type = None

            # Restart sleep timer
            self._reset_sleep_timer()

        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}", exc_info=True)
            raise

        finally:
            self.is_processing = False
            # If there are new messages in queue, start new processing task
            if self.combined_message != "":
                self.logger.info(f"combined_message: {self.combined_message}")
                asyncio.create_task(self._process_message())

    async def _wakeup_timer(self, to_awake: bool = True) -> None:
        """Wait time to wake up
        Args:
            to_awake: Whether to wake up, True means wake up, False means stay asleep
        """
        self.logger.info(f"To wakeup timer is {self.to_wakeup_secs} seconds for bot {self.bot.id}")
        while self.to_wakeup_secs > 0:
            await asyncio.sleep(1)
            self.to_wakeup_secs -= 1

        self.logger.info(f"To wakeup timer is over for bot {self.bot.id}")
        if to_awake:
            self.is_awake = True
            self.logger.info(f"Bot {self.bot.id} has woken up")
            return
        else:
            self.is_awake = False
            self.logger.info(f"Bot {self.bot.id} has entered sleep mode")
            return

    async def _wait_wakeup_timer(self, to_wakeup_secs: Optional[int] = None) -> None:
        """Wait for wakeup timer
        Args:
            to_wakeup_secs: Wake up time, None means default value
        """
        if self.is_awake:
            self.logger.info("Bot is awake, skipping wakeup timer")
            return
        if not self.context:
            self.to_wakeup_secs = 0
            self.logger.info("Bot is not awake, setting to wakeup timer to 0")
            await self._wakeup_timer()
            return

        if self.wakeup_task and not self.wakeup_task.done():
            self.wakeup_task.cancel()
            await asyncio.sleep(0)
            self.logger.info("Cancelled existing wakeup timer.")

        if to_wakeup_secs is not None:
            self.to_wakeup_secs = to_wakeup_secs
            self.logger.info(
                f"Setting fixed wakeup timer for {to_wakeup_secs} seconds for bot {self.bot.id}"
            )
            self.wakeup_task = asyncio.create_task(self._wakeup_timer())
            self.logger.info("Created new wakeup timer")
            await self.wakeup_task
            return

        else:
            if not self.to_wakeup_secs:
                # Get wake up time from mapping based on relationship type and level
                relationship_map = self.relationship_wakeup_times.get(
                    self.relationship_type, self.relationship_wakeup_times["default"]
                )

                self.to_wakeup_secs = relationship_map.get(
                    self.relationship_level, relationship_map["default"]
                )

            random_number: int = random.randint(1, 100)
            to_wakeup: bool = True

            # 50% chance to keep original value, 50% chance to adjust randomly
            if random_number <= 50:
                self.to_wakeup_secs = max(int(self.to_wakeup_secs * random_number / 50), 1)

            # 5% chance to not wake up
            if random_number <= 5:
                to_wakeup = False

            self.wakeup_task = asyncio.create_task(self._wakeup_timer(to_wakeup))
            self.logger.info("Created new wakeup timer")
            await self.wakeup_task

    async def _process_timer(self, to_process_secs: int) -> None:
        """Message processing timer"""
        try:
            # Wait for message processing
            await asyncio.sleep(to_process_secs)
            self.include_message_time = True
            # Load emotion data if not already loaded
            if not self.loaded_emotions:
                await self._load_emotions()
            # Refresh relationship after bot initialized
            if not self.calculated_passive_scores:
                self._calculate_passive_scores()
                self._refresh_relationship()
                self.calculated_passive_scores = True
                self.logger.info("Refreshed relationship because bot initialized")
            # Refresh relationship when has emotions
            elif self.emotions:  # Check both is not None and not empty
                self._calculate_passive_scores()
                self._refresh_relationship()
                self.logger.info("Refreshed relationship because has emotions", emotions=self.emotions)
            else:
                self.logger.info("No need to refresh relationship")
            # If bot is not awake, wait for wake up
            if not self.is_awake:
                await self._wait_wakeup_timer()
            # If no processing is currently running, start processing
            if not self.is_processing and self.combined_message != "":
                asyncio.create_task(self._process_message())
        except Exception as e:
            self.logger.error(f"Error in process timer: {str(e)}", exc_info=True)
            raise

    def _reset_process_timer(
        self, secs_main: int | None = None, secs_sub: int | None = None, secs_adjust: int | None = None
    ) -> None:
        """Reset message processing timer
        Args:
            secs_main: Main message processing time, None means no operation, 0 means cancel, others mean set
            secs_sub: Sub message processing time, None means no operation, 0 means cancel, others mean set
            secs_adjust: Adjust main message processing time, None means no operation, 0 means cancel, others mean set
        """
        # Cancel existing sub message processing task
        if secs_sub is not None and self.process_task_sub and not self.process_task_sub.done():
            self.process_task_sub.cancel()
            self.logger.info("Cancelled existing process_task_sub.")
        # Cancel existing main message processing task
        if (
            (secs_main is not None or secs_adjust is not None)
            and self.process_task_main
            and not self.process_task_main.done()
        ):
            self.process_task_main.cancel()
            self.logger.info("Cancelled existing process_task_main.")
            if secs_adjust is not None:
                secs_main = secs_adjust
        # Create new main message processing task
        if secs_main:
            self.process_task_main = asyncio.create_task(self._process_timer(secs_main))
            self.logger.info(f"New process_task_main created. secs: {secs_main}")
        # Create new sub message processing task
        if secs_sub and self.process_task_main:
            self.process_task_sub = asyncio.create_task(self._process_timer(secs_sub))
            self.logger.info(f"New process_task_sub created. secs: {secs_sub}")

    async def receive_message(self, received_message: dict) -> None:
        """Entry function, receive message"""
        self.logger.info(f"Received message: {received_message}")

        try:
            content = received_message.get("content", "")
            message_time = received_message.get("message_time")
            message_type = MessageType.parse(received_message.get("message_type", ""))

            if not message_time:
                self.logger.warning("Skipping process message due to missing content or message_time.")
            elif not message_type:
                self.logger.warning("Skipping process message due to missing message_type.")

            # Process chat\chat_notyping messages
            elif content and message_type.category == MessageTypeCategory.CONTENT:
                # Cancel sleep timer setting
                self._reset_sleep_timer(0)

                # Cancel existing message processing tasks
                self._reset_process_timer(0, 0)

                # Combine messages
                async with self.combining_lock:
                    if self.include_message_time is True:
                        self.combined_message += f"[{self._convert_timestamp(message_time)}]\n"
                        self.include_message_time = False
                    self.combined_message += self.message_tag + f"{content}"
                self.logger.info("Message appended to the message queue.")

                # Create new message processing task
                if message_type == MessageType.CHAT:
                    self._reset_process_timer(self.chat_secs)
                else:
                    self._reset_process_timer(self.chat_notyping_secs)

            elif not self.last_message_type:
                self.logger.info("Skipping process message due to missing last_message_type.")

            # Process typing_end message
            elif self.last_message_type == MessageType.TYPING and message_type == MessageType.TYPING_END:
                self._reset_process_timer(None, self.typing_end_secs)

            # Process when last message is chat and current message is typing
            elif self.last_message_type == MessageType.CHAT and message_type == MessageType.TYPING:
                self._reset_process_timer(None, self.typing_secs_short, self.typing_secs_total)
            # If last message is typing_end and current message is typing
            elif self.last_message_type == MessageType.TYPING_END and message_type == MessageType.TYPING:
                self._reset_process_timer(None, self.typing_secs_short)

            # Record last message type
            self.last_message_type = message_type

        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}", exc_info=True)
