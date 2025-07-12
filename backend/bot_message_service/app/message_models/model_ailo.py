import json
import random
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Callable, Awaitable, List

from .context_strategy import ContextStrategyProtocol, TaskDefinition
from .model_ailo_mixins.context_mixin import ContextMixin
from .model_ailo_mixins.db_mixin import DBMixin
from .model_ailo_mixins.llm_mixin import LLMMixin
from .model_ailo_mixins.message_mixin import MessageMixin
from .model_ailo_mixins.relationship_mixin import RelationshipMixin
from .base import BaseModel
from ..utils.logging import get_logger, bind_context
from ..llm_apis import model_ailo_advanced_llm as advanced_llm
from ..enums import (
    MessageType,
    MessageTypeCategory,
    RelationshipType,
    FriendLevel,
    RomanceLevel,
    TaskType,
    TypingStatus,
)

logger = get_logger(__name__)


class ModelAilo(ContextMixin, DBMixin, LLMMixin, MessageMixin, RelationshipMixin, BaseModel):
    def __init__(self, bot: Any, message_service: str, cleanup_callback: Callable[[str], Awaitable[None]]):
        """Initialize the Ailo model
        Args:
            bot: Bot instance from the database. This is treated as the initial, read-only state.
            message_service: Message service type
            cleanup_callback: Cleanup callback function
        """
        # Call parent class initialization method
        super().__init__(message_service=message_service, bot=bot, cleanup_callback=cleanup_callback)

        # Create a context-bound logger for this bot instance
        self.logger = bind_context(logger, bot_id=self.bot.id, entity_id=self.bot.entity_id)
        self.logger.info("Initialized ModelAilo instance")

        # === TIMER CONFIGS ===
        # Relationship type and level to wakeup time mapping
        self.to_wakeup_secs = {
            # Friend relationship wakeup time mapping
            RelationshipType.FRIEND.value: {
                FriendLevel.HOSTILE.value: 120,
                FriendLevel.COLD.value: 100,
                FriendLevel.NEUTRAL.value: 50,
                FriendLevel.FRIENDLY.value: 10,
                FriendLevel.WARM.value: 10,
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
        self.to_sleep_secs: int = 120  # Sleep timeout

        # Message processing timing configuration
        self.request_secs = {
            MessageType.CHAT: 3,
            MessageType.CHAT_NOTYPING: 8,
            MessageType.TYPING: {"total": 32, "short": 16},
            MessageType.TYPING_END: 3,
        }

        # === RELATIONSHIP CONFIGS ===
        # Passive score change configuration
        self.passive_score_config = {
            "friend_decay": {
                "cool_down_days": 3,  # Grace period in days
                "change_rate": -5,  # Points to subtract per day if above neutral
            },
            "friend_increase": {
                "cool_down_days": 3,  # Grace period in days
                "change_rate": 5,  # Points to subtract per day if below neutral
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

        # Passive score decay trough ratio
        self.friend_passive_ratio: float = 0.4
        self.romance_passive_ratio: float = 0.3

        # Relationship level change buffer
        self.friend_level_up_buffer: float = 1.05
        self.friend_level_down_buffer: float = 0.95
        self.romance_level_up_buffer: float = 1.05
        self.romance_level_down_buffer: float = 0.95

        # === CONTEXT CONFIGS ===
        self.message_tag: str = "[msg]"  # Message separator
        # Constants for message handling
        self.attack_content_replacement = "[Deleted prompt attack content]"
        self.timestamp_format = "%Y-%m-%d %H:%M:%S"  # Timestamp format constants
        self.timestamp_regex = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]"
        self.memory_limit: int = 2000  # Memory limit
        self.context_limit: int = 9000  # Context limit
        # Number of context not removed when summary to memory,
        # recommend using even number to reserve the messages between both sides
        self.context_expire_num: int = 12
        self.context_expire_hours: int = 10  # Context expire this time will be removed
        self.min_summary_hours: int = 4  # Minimum summarize interval
        self.summary_time_point: int = 4  # Start summarize must go through this time point

        # === LLM CONFIGS ===
        # LLM parameters configuration for different models
        self.llm_params_config = {
            "thinking": {
                "thinking": {"type": "disabled"},
            },
            "dont_thinking": {
                "thinking": {"type": "disabled"},
            },
        }

        self.llm_max_retries: int = 1  # Maximum number of retries
        self.llm_retry_delay_secs: int = 2  # Delay between retries in seconds

        # === REPLY CONFIGS ===
        self.typing_speed: float = 0.6  # Seconds per character
        self.prepared_wait_min: float = 4.0  # Minimum wait time before sending prepared messages
        self.prepared_wait_max: float = 16.0  # Maximum wait time before sending prepared messages
        self.timestamp_add_threshold_secs: int = (
            300  # Add timestamp if time since last > this value (in seconds)
        )

        # === VARIABLES AND FLAGS ===
        # In-memory state for the bot instance.
        # These attributes are copied from the initial bot object to create a transactional
        # working copy. All operations during the instance's lifecycle are performed
        # on these attributes. They are persisted back to the database only when the
        # instance is about to sleep, preventing dirty reads and batching DB writes.
        try:
            # For mandatory attributes, direct access ensures that if the DB object is
            # missing a field (e.g., due to schema mismatch), it fails immediately.
            # Initialize context and context_metadata with safe defaults if None
            self.context: Dict = bot.context if bot.context is not None else {"messages": []}
            self.context_metadata: list = bot.context_metadata if bot.context_metadata is not None else []
            self.friend_score: int = bot.friend_score
            self.romance_score: int = bot.romance_score
            self.friend_score_cap: int = bot.friend_score_cap
            self.friend_score_floor: int = bot.friend_score_floor
            self.romance_score_cap: int = bot.romance_score_cap
            self.friend_score_peak: int = bot.friend_score_peak
            self.friend_score_trough: int = bot.friend_score_trough
            self.romance_score_peak: int = bot.romance_score_peak
            self.relationship_type: str = bot.relationship_type
            self.relationship_level: str = bot.relationship_level
            self.friend_level: str = bot.friend_level
            self.friend_buffer_status: str = bot.friend_buffer_status
            self.romance_buffer_status: str = bot.romance_buffer_status
            self.is_polite: bool = bool(bot.is_polite)
            self.is_crushing: bool = bool(bot.is_crushing)

            # For optional/nullable attributes, initialize with a default value
            # if the attribute doesn't exist on the bot object.
            self.memory: str = getattr(bot, "memory", "")
            self.relationship_style: str = getattr(bot, "relationship_style", "")
            self.romance_level: Optional[str] = getattr(bot, "romance_level", None)
            self.last_chat_time: Optional[datetime] = getattr(bot, "last_chat_time", None)

        except AttributeError as e:
            self.logger.critical(
                "bot_object_missing_attribute",
                error=f"The 'bot' object is missing a required attribute during ModelAilo initialization: {e}",
                exc_info=True,
            )
            # Re-raising is crucial. We cannot create a valid model instance without mandatory attributes.
            raise

        self.emotions: Dict[str, Dict[str, Any]] = {}
        # The logic to ensure peak/trough are at least the current score is a sanity check,
        # not initialization. It should come after the strict initialization from the bot object.
        self.friend_score_peak: int = max(self.friend_score_peak, self.friend_score)
        self.friend_score_trough: int = min(self.friend_score_trough, self.friend_score)
        self.romance_score_peak: int = max(self.romance_score_peak, self.romance_score)

        # Calculated values used for relationship computation but not stored in database
        # These values are recalculated before each conversation by calculate_emotions_and_scores
        self.friend_score_calc: int = self.friend_score
        self.romance_score_calc: int = self.romance_score

        # Whether the current message is the first message after bot created
        self.initial_message: bool = True if not self.context else False
        self.current_wakeup_secs: int = 0  # Current wakeup time
        self.is_awake: bool = False  # Whether bot is awake
        self.combined_message: str = ""  # Combined message from user
        self.combining_lock: asyncio.Lock = asyncio.Lock()
        self.last_message_type: Optional[MessageType] = None
        self.include_message_time = True

        self.sleep_task: asyncio.Task | None = None  # Sleep task
        self.wakeup_task: asyncio.Task | None = None  # Wakeup task
        self.processing_main_task: asyncio.Task | None = None  # Main message processing task
        self.processing_sub_task: asyncio.Task | None = None  # Fast message processing task
        self.requesting_task: asyncio.Task | None = None  # Request llm task

        self.loaded_emotions: bool = False
        self.calculated_passive_scores: bool = False
        self.need_extra_info: bool = False
        self.need_summary: bool = False  # Whether summary is needed
        self.context_strategy_instance: Optional[ContextStrategyProtocol] = None
        self.instant_context: str = ""
        self.llm_task_result: dict = {}

        self.start_typing_time: Optional[datetime] = None
        self.unsent_message: str = ""
        self.reply_task: asyncio.Task | None = None
        self.tying_task: asyncio.Task | None = None
        self.typing_queue: Dict[str, List[Dict[str, str]]] = {
            "reply_messages": [],
            "prepared_messages": [],
        }  # Queue for typing message
        self.typing_queue_lock: asyncio.Lock = asyncio.Lock()
        self.is_typing_queue_saved: bool

        # Verify context and metadata consistency on initialization
        self._verify_and_repair_metadata()

        self.logger.debug(
            "Initialized ModelAilo instance",
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
            self.logger.info("sleep_timer_started", to_sleep_secs=to_sleep_secs)
            await asyncio.sleep(to_sleep_secs)

            # Persist all in-memory changes to the database before sleeping.
            await self._save_bot_state()

            # Execute cleanup callback
            if self.cleanup_callback:
                try:
                    await self.cleanup_callback(str(self.bot.entity_id))
                    self.logger.info("cleanup_callback_executed")
                except Exception as e:
                    self.logger.error("cleanup_callback_failed", error=str(e), exc_info=True)
                    raise

            self.logger.info("bot_sleep_mode_entered")

        except asyncio.CancelledError:
            self.logger.info("sleep_timer_cancelled")
            raise
        except Exception as e:
            self.logger.error("sleep_timer_failed", error=str(e), exc_info=True)
            raise

    def _reset_sleep_timer(self, to_sleep_secs: Optional[int] = None) -> None:
        """Reset sleep timer
        Args:
            to_sleep_secs: Sleep time, None means default value, 0 means cancel sleep timer
        """
        self.logger.info("sleep_timer_resetting")
        if self.sleep_task and not self.sleep_task.done():
            self.sleep_task.cancel()
            self.logger.info("previous_sleep_timer_cancelled")

        if to_sleep_secs is None:
            to_sleep_secs = self.to_sleep_secs

        if to_sleep_secs > 0:
            self.sleep_task = asyncio.create_task(self._sleep_timer(to_sleep_secs))
            self.logger.info("new_sleep_timer_set", to_sleep_secs=to_sleep_secs)

    async def _process_reply(self) -> None:
        """
        Orchestrates the entire process of replying, including sending messages
        and saving the final context. This function is designed to be a self-contained task.
        """
        try:
            # Cancel sleep timer setting
            self._reset_sleep_timer(0)

            # Copy the unsent message before sending
            previous_unsent_message = self.unsent_message

            # --- Step 1: Check if a reply should be sent ---
            reply_decision_key = TaskDefinition.get_response_key(TaskType.REPLY_DECISION)
            reply_content_key = TaskDefinition.get_response_key(TaskType.REPLY_CONTENT)
            want_reply = self.llm_task_result.get(reply_decision_key)
            has_content = bool(self.llm_task_result.get(reply_content_key))

            if want_reply and has_content:
                # --- Step 2: Populate queue and create send task ---
                async with self.typing_queue_lock:
                    self.typing_queue["reply_messages"].clear()
                    self.typing_queue["prepared_messages"].clear()
                    # Populate with new messages from the latest LLM result
                    reply_content = self.llm_task_result.get(reply_content_key, "")
                    messages = str(reply_content).split(self.message_tag)
                    for msg in messages:
                        if msg:
                            self.typing_queue["reply_messages"].append(
                                {"content": msg, "status": TypingStatus.PENDING.value}
                            )
                    prepared_content = self.llm_task_result.get(
                        TaskDefinition.get_response_key(TaskType.PREPARED_CONTENT), ""
                    )
                    messages = str(prepared_content).split(self.message_tag)
                    for msg in messages:
                        if msg:
                            self.typing_queue["prepared_messages"].append(
                                {"content": msg, "status": TypingStatus.PENDING.value}
                            )
                    self.logger.info("Populated typing queue", queue=self.typing_queue)

                wait_secs = random.uniform(self.prepared_wait_min, self.prepared_wait_max)
                self.tying_task = asyncio.create_task(self._process_typing_queue(wait_secs))

                try:
                    # Await the typing task. This is the point that will be interrupted.
                    await self.tying_task
                except asyncio.CancelledError:
                    # This is an expected interruption. Log it and continue to the saving logic.
                    self.logger.info(
                        "typing_task_interrupted_by_new_request",
                        reason="Proceeding to save state.",
                    )

            else:
                self.logger.info("reply_sending_skipped", want_reply=want_reply, has_content=has_content)

            if self.llm_task_result.get(TaskDefinition.get_response_key(TaskType.IS_ATTACK)):
                self._process_attack_context()

            # --- Early exit if nothing was sent ---
            # This check is crucial after the await, especially if the task was cancelled.
            async with self.typing_queue_lock:
                was_anything_sent = any(
                    msg["status"] == TypingStatus.SENT.value for msg in self.typing_queue["reply_messages"]
                ) or any(
                    msg["status"] == TypingStatus.SENT.value
                    for msg in self.typing_queue["prepared_messages"]
                )

            if not was_anything_sent:
                self.logger.info("no_messages_were_sent_skipping_save")
                return

            # --- Step 3: Save context (formerly _save_typing_queue) ---
            # This logic now runs regardless of whether the typing task was completed or cancelled.
            async with self.typing_queue_lock:
                # Reconstruct the response from what was actually sent
                sent_reply_messages = [
                    msg["content"]
                    for msg in self.typing_queue["reply_messages"]
                    if msg["status"] == TypingStatus.SENT.value
                ]
                sent_prepared_messages = [
                    msg["content"]
                    for msg in self.typing_queue["prepared_messages"]
                    if msg["status"] == TypingStatus.SENT.value
                ]
                self.llm_task_result[TaskDefinition.get_response_key(TaskType.REPLY_CONTENT)] = (
                    self.message_tag.join(sent_reply_messages)
                )
                self.llm_task_result[TaskDefinition.get_response_key(TaskType.PREPARED_CONTENT)] = (
                    self.message_tag.join(sent_prepared_messages)
                )
                self.logger.info("reconstructed_llm_task_result_from_sent_messages")

            self._append_response_to_context(self.llm_task_result)
            self._process_emotions_and_score(self.llm_task_result)

            # Refresh relationship, check both is not None and not empty
            if not (not self.emotions or len(self.emotions) <= 1 and "none" in self.emotions):
                self._calculate_passive_scores()
                self._refresh_relationship()
                self.logger.info(
                    "relationship_refreshed_before_request_with_emotions", emotions=self.emotions
                )
            else:
                self.logger.info("relationship_refresh_skipped_before_request", emotions=self.emotions)

            if self.initial_message:
                self.initial_message = False

            self.logger.info("typing_queue_processing_and_saving_complete")

            # Clear up if it has something before sending and nothing changed
            if previous_unsent_message and previous_unsent_message == self.unsent_message:
                self.unsent_message = ""

        except Exception as e:
            # Catch any other unexpected errors during the reply process
            self.logger.error("An unexpected error occurred in _process_reply", error=str(e), exc_info=True)
        finally:
            # Save summary to memory
            self._summary_to_memory(self.llm_task_result)
            # Restart sleep timer regardless of how the task finished.
            self._reset_sleep_timer()

    async def _process_request(self) -> None:
        """Process message"""
        try:
            # End other timers and reset the last message type
            self.last_message_type = None  # To Calculate waiting time
            self.include_message_time = True
            self._reset_request_timer(0, 0)

            # --- Interruption Handling ---
            if self.tying_task and not self.tying_task.done():
                self.logger.info("previous_reply_task_is_running_handling_interruption")
                # 1. Clean up the queue state from the interrupted task.
                await self._handle_interrupted_reply()
                # 2. Cancel the old reply task and wait for it to finish cancelling.
                self.tying_task.cancel()
                try:
                    await self.tying_task
                except asyncio.CancelledError:
                    self.logger.info("successfully_cancelled_previous_reply_task")

            # Wait for the reply task to finish
            if self.reply_task and not self.reply_task.done():
                await self.reply_task

            # Update context
            self._varify_context()
            async with self.combining_lock:
                self._append_context("user", self.combined_message)
                self.combined_message = ""
            self.logger.info("context_updated_with_user_message")

            # If bot is not awake, don't respond
            if not self.is_awake:
                self.logger.info("bot_is_sleeping_skipping_response")
                # Restart sleep timer
                self._reset_sleep_timer()
                return

            # Refresh system context (now includes unsent_message from interruption)
            self._refresh_system_context()

            # If the current message use thinking mode
            if self.initial_message:
                llm_kwargs = self.llm_params_config["thinking"]
            else:
                llm_kwargs = self.llm_params_config["dont_thinking"]

            response_content = await self._get_response_content(advanced_llm, **llm_kwargs)

            if not response_content:
                self.logger.error("failed_to_generate_valid_response_after_retries")
                return

            self.llm_task_result = json.loads(response_content)
            self.logger.debug("llm_task_result_received", llm_task_result=self.llm_task_result)

            # Send reply
            self.logger.debug("creating_new_reply_task")
            self.reply_task = asyncio.create_task(self._process_reply())

        except asyncio.CancelledError:
            self.logger.info("message_processing_task_cancelled")
            raise
        except Exception as e:
            self.logger.error("error_processing_message", error=str(e), exc_info=True)
            raise

    async def _wakeup_timer(self, to_awake: bool = True) -> None:
        """Wait time to wake up
        Args:
            to_awake: Whether to wake up, True means wake up, False means stay asleep
        """
        self.logger.info("wakeup_timer_started", to_wakeup_secs=self.current_wakeup_secs)
        while self.current_wakeup_secs > 0:
            await asyncio.sleep(1)
            self.current_wakeup_secs -= 1

        self.logger.info("wakeup_timer_finished")
        if to_awake:
            self.is_awake = True
            self.logger.info("bot_has_woken_up")
            return
        else:
            self.is_awake = False
            self.logger.info("bot_has_entered_sleep_mode")
            return

    async def _waiting_wakeup_timer(self, to_wakeup_secs: Optional[int] = None) -> None:
        """Wait for wakeup timer
        Args:
            to_wakeup_secs: Wake up time, None means default value
        """
        if self.is_awake:
            self.logger.info("bot_is_awake_skipping_wakeup_timer")
            return
        if self.initial_message:
            self.current_wakeup_secs = 0
            self.logger.info("bot_not_awake_setting_wakeup_timer_to_zero")
            await self._wakeup_timer()
            return

        if self.wakeup_task and not self.wakeup_task.done():
            self.wakeup_task.cancel()
            await asyncio.sleep(0)
            self.logger.debug("cancelled_existing_wakeup_timer")

        if to_wakeup_secs is not None:
            self.current_wakeup_secs = to_wakeup_secs
            self.logger.info("setting_fixed_wakeup_timer", to_wakeup_secs=to_wakeup_secs)
            self.wakeup_task = asyncio.create_task(self._wakeup_timer())
            self.logger.info("created_new_wakeup_timer")
            await self.wakeup_task
            return

        else:
            if not self.current_wakeup_secs:
                # Get wake up time from mapping based on relationship type and level
                relationship_map = self.to_wakeup_secs.get(
                    self.relationship_type, self.to_wakeup_secs["default"]
                )

                self.current_wakeup_secs = relationship_map.get(
                    self.relationship_level, relationship_map["default"]
                )

            random_number: int = random.randint(1, 100)
            to_wakeup: bool = True

            # 50% chance to keep original value, 50% chance to adjust randomly
            if random_number <= 50:
                self.current_wakeup_secs = max(int(self.current_wakeup_secs * random_number / 50), 1)

            # 5% chance to not wake up
            if random_number <= 5:
                to_wakeup = False
                self.logger.warning("bot_will_not_wake_up", random_number=random_number)

            self.wakeup_task = asyncio.create_task(self._wakeup_timer(to_wakeup))
            self.logger.info("created_new_wakeup_timer")
            await self.wakeup_task

    async def _request_timer(self, to_process_secs: int) -> None:
        """Message processing timer"""
        try:
            # Wait for message processing
            await asyncio.sleep(to_process_secs)
            # Load emotion data if not already loaded
            if not self.loaded_emotions:
                await self._load_emotions()
            # Refresh relationship after bot initialized
            if not self.calculated_passive_scores:
                self._calculate_passive_scores()
                self._refresh_relationship()
                self.calculated_passive_scores = True
                self.logger.info("refreshed_relationship_on_bot_initialization")
            else:
                self.logger.info("relationship_refresh_skipped_before_processing", emotions=self.emotions)
            # If bot is not awake, wait for wake up
            if not self.is_awake:
                await self._waiting_wakeup_timer()
            # If no processing is currently running, start processing
            if self.combined_message != "":
                # If a request is already in progress, cancel it to start a new one.
                if self.requesting_task and not self.requesting_task.done():
                    self.logger.info("new_message_processing_request_cancelling_previous")
                    self.requesting_task.cancel()
                    try:
                        await self.requesting_task  # Wait for the task to acknowledge cancellation
                    except asyncio.CancelledError:
                        self.logger.info("successfully_awaited_cancellation_of_previous_task")

                # Create a new task.
                self.logger.info("starting_new_message_processing_task")
                self.requesting_task = asyncio.create_task(self._process_request())
        except asyncio.CancelledError:
            self.logger.debug("processing_timer_was_cancelled")
        except Exception as e:
            self.logger.error("error_in_process_timer", error=str(e), exc_info=True)
            raise

    def _reset_request_timer(
        self, secs_main: int | None = None, secs_sub: int | None = None, secs_adjust: int | None = None
    ) -> None:
        """Reset message processing timer
        Args:
            secs_main: Main message processing time, None means no operation, 0 means cancel, others mean set
            secs_sub: Sub message processing time, None means no operation, 0 means cancel, others mean set
            secs_adjust: Adjust main message processing time, None means no operation, 0 means cancel, others mean set
        """
        # Cancel existing sub message processing task
        if secs_sub is not None and self.processing_sub_task and not self.processing_sub_task.done():
            self.processing_sub_task.cancel()
            self.logger.debug("cancelled_existing_processing_task_sub")
        # Cancel existing main message processing task
        if (
            (secs_main is not None or secs_adjust is not None)
            and self.processing_main_task
            and not self.processing_main_task.done()
        ):
            self.processing_main_task.cancel()
            self.logger.debug("cancelled_existing_processing_task_main")
            if secs_adjust is not None:
                secs_main = secs_adjust
        # Create new main message processing task
        if secs_main:
            self.processing_main_task = asyncio.create_task(self._request_timer(secs_main))
            self.logger.info("new_processing_task_main_created", secs=secs_main)
        # Create new sub message processing task
        if secs_sub and self.processing_main_task:
            self.processing_sub_task = asyncio.create_task(self._request_timer(secs_sub))
            self.logger.info("new_processing_task_sub_created", secs=secs_sub)

    async def receive_message(self, received_message: dict) -> None:
        """Entry function, receive message"""
        self.logger.info("received_message", message=received_message)

        try:
            content = received_message.get("content", "")
            message_time = received_message.get("message_time")
            message_type = MessageType.parse(received_message.get("message_type", ""))

            if not message_time:
                self.logger.warning("skipping_process_message_due_to_missing_content_or_message_time")
            elif not message_type:
                self.logger.warning("skipping_process_message_due_to_missing_message_type")

            # Process chat\chat_notyping messages
            elif content and message_type.category == MessageTypeCategory.CONTENT:
                # Cancel sleep timer setting
                self._reset_sleep_timer(0)

                # Cancel existing message processing tasks
                self._reset_request_timer(0, 0)

                # Combine messages
                async with self.combining_lock:
                    if self.include_message_time:
                        self.combined_message += f"[{self._convert_timestamp(message_time)}]{content}"
                        self.include_message_time = False
                    else:
                        self.combined_message += self.message_tag + f"{content}"
                self.logger.info("message_appended_to_the_message_queue")

                # Create new message processing task
                if message_type == MessageType.CHAT:
                    self._reset_request_timer(self.request_secs[MessageType.CHAT])
                else:
                    self._reset_request_timer(self.request_secs[MessageType.CHAT_NOTYPING])

            elif not self.last_message_type:
                self.logger.info("skipping_process_message_due_to_missing_last_message_type")

            # Process typing_end message
            elif self.last_message_type == MessageType.TYPING and message_type == MessageType.TYPING_END:
                self._reset_request_timer(None, self.request_secs[MessageType.TYPING_END])

            # Process when last message is chat and current message is typing
            elif self.last_message_type == MessageType.CHAT and message_type == MessageType.TYPING:
                self._reset_request_timer(
                    None,
                    self.request_secs[MessageType.TYPING]["short"],
                    self.request_secs[MessageType.TYPING]["total"],
                )
            # If last message is typing_end and current message is typing
            elif self.last_message_type == MessageType.TYPING_END and message_type == MessageType.TYPING:
                self._reset_request_timer(None, self.request_secs[MessageType.TYPING]["short"])

            # Record last message type
            self.last_message_type = message_type

        except Exception as e:
            self.logger.error("error_processing_message", error=str(e), exc_info=True)
