from typing import Any, Dict, Optional, Callable, Coroutine, List, Protocol, Tuple, Awaitable
from datetime import datetime
import asyncio

from enums import MessageType
from .context_strategy import ContextStrategyProtocol


class ModelAiloLike(Protocol):
    """Protocol defining the required attributes and methods for ModelAilo.
    This protocol defines all attributes and method signatures that ModelAilo class needs,
    allowing Mixins to have proper type checking.
    """

    # === Attributes from ModelAilo.__init__ ===
    # Bot and service related
    bot: Any
    message_service: str
    cleanup_callback: Callable[[str], Awaitable[None]]
    logger: Any

    # Core state attributes
    context: Dict
    context_metadata: list
    friend_score: int
    romance_score: int
    friend_score_cap: int
    friend_score_floor: int
    romance_score_cap: int
    friend_score_peak: int
    friend_score_trough: int
    romance_score_peak: int
    relationship_type: str
    relationship_level: str
    friend_level: str
    friend_buffer_status: str
    romance_buffer_status: str
    is_polite: bool
    is_crushing: bool
    memory: str
    relationship_style: str
    romance_level: Optional[str]
    last_chat_time: Optional[datetime]
    friend_score_calc: int
    romance_score_calc: int
    emotions: Dict[str, Dict[str, Any]]

    # Message handling & state
    typing_queue: Dict[str, List[Dict[str, str]]]
    typing_queue_lock: asyncio.Lock
    message_tag: str
    unsent_message: str
    initial_message: bool
    is_awake: bool
    combined_message: str
    combining_lock: asyncio.Lock
    last_message_type: Optional[MessageType]
    include_message_time: bool

    # Task related
    sleep_task: Optional[asyncio.Task]
    wakeup_task: Optional[asyncio.Task]
    processing_main_task: Optional[asyncio.Task]
    processing_sub_task: Optional[asyncio.Task]
    requesting_task: Optional[asyncio.Task]
    reply_task: Optional[asyncio.Task]
    tying_task: Optional[asyncio.Task]

    # State flags and data
    loaded_emotions: bool
    calculated_passive_scores: bool
    need_summary: bool
    context_strategy_instance: Optional[ContextStrategyProtocol]
    instant_context: str
    llm_task_result: dict
    # Configuration
    passive_score_config: Dict[str, Dict[str, int]]
    friend_passive_ratio: float
    romance_passive_ratio: float
    friend_level_up_buffer: float
    friend_level_down_buffer: float
    romance_level_up_buffer: float
    romance_level_down_buffer: float
    llm_max_retries: int
    llm_retry_delay_secs: int
    attack_content_replacement: str
    timestamp_format: str
    emotion_calculation_rules: Dict[str, Dict[str, Any]]
    memory_limit: int
    context_limit: int
    context_expire_num: int
    context_expire_hours: int
    min_summary_hours: int
    summary_time_point: int
    need_extra_info: bool
    typing_speed: float

    # Contact related attributes
    user_profile: Optional[Dict[str, Any]]
    profile_changes: str

    # === Method Signatures from Mixins ===

    # from message_mixin.py
    def _send_message(  # noqa: E704
        self, content: Optional[str] = "", message_type: MessageType = MessageType.CHAT
    ) -> Coroutine[Any, Any, None]: ...  # noqa: E704

    def _send_message_queue(self, message_type_key: str) -> Coroutine[Any, Any, None]: ...  # noqa: E704

    def _process_typing_queue(self, wait_secs: float) -> Coroutine[Any, Any, None]: ...  # noqa: E704

    def _handle_interrupted_reply(self) -> Coroutine[Any, Any, None]: ...  # noqa: E704

    # from db_mixin.py
    def _load_emotions(self) -> Coroutine[Any, Any, None]: ...  # noqa: E704

    def _save_bot_state(self) -> Coroutine[Any, Any, None]: ...  # noqa: E704

    # from llm_mixin.py
    def _generate_response(self, llm: Any, **kwargs: Any) -> Coroutine[Any, Any, str]: ...  # noqa: E704

    def _validate_content(self, response: str | None) -> Coroutine[Any, Any, bool]: ...  # noqa: E704

    def _get_response_content(  # noqa: E704
        self, llm: Any, **kwargs: Any
    ) -> Coroutine[Any, Any, Optional[str]]: ...

    # from context_mixin.py
    def _convert_timestamp(self, timestamp: str | None = None) -> str: ...  # noqa: E704

    def _create_fingerprint(self, text: str) -> str: ...  # noqa: E704

    def _verify_single_metadata(self, message: dict, metadata: dict) -> bool: ...  # noqa: E704

    def _create_repaired_metadata(self, message: dict) -> dict: ...  # noqa: E704

    def _verify_and_repair_metadata(self) -> None: ...  # noqa: E704

    def _create_instant_context(self) -> str: ...  # noqa: E704

    def _refresh_system_context(self) -> None: ...  # noqa: E704

    def _varify_context(self) -> None: ...  # noqa: E704

    def _append_context(self, role: str, context_content: str) -> None: ...  # noqa: E704

    def _append_response_to_context(self, llm_task_result: dict) -> None: ...  # noqa: E704

    def _process_attack_context(self) -> None: ...  # noqa: E704

    def _remove_oldest_context(self) -> bool: ...  # noqa: E704

    def _remove_expire_context(self, include_important: bool = False) -> None: ...  # noqa: E704

    def _summary_to_memory(self, llm_task_result: dict) -> None: ...  # noqa: E704

    # from relationship_mixin.py
    def _ensure_datetime(self, dt_value: Any) -> Optional[datetime]: ...  # noqa: E704

    def _get_passive_score_change(self, days: int) -> Tuple[int, int]: ...  # noqa: E704

    def _calculate_passive_scores(self) -> None: ...  # noqa: E704

    def _get_level_from_score(  # noqa: E704
        self, score: int, rel_type: str
    ) -> Optional[Dict[str, Any]]: ...

    def _get_level_by_name(  # noqa: E704
        self, level_name: Optional[str], rel_type: str
    ) -> Optional[Dict[str, Any]]: ...

    def _apply_buffer(  # noqa: E704
        self,
        current_rel: Optional[Dict[str, Any]],
        stable_level_name: Optional[str],
        buffer_status: str,
        score: int,
        level_up_buffer: float,
        level_down_buffer: float,
        rel_type: str,
    ) -> Tuple[Optional[str], str]: ...

    def _refresh_relationship(self) -> None: ...  # noqa: E704

    def _format_emotions_config(self, config: Optional[Dict[str, Any]]) -> Dict[str, Any]: ...  # noqa: E704

    def _new_anger_emotion(  # noqa: E704
        self, anger_emotion_score: int, friend_score_change: int, romance_score_change: int
    ) -> None: ...

    def _process_emotions_and_score(self, response_result: dict) -> None: ...  # noqa: E704

    # from contact_mixin.py
    def _initialize_user_profile(self) -> Coroutine[Any, Any, None]: ...  # noqa: E704

    def _fetch_user_profile(  # noqa: E704
        self, user_entity_id: str
    ) -> Coroutine[Any, Any, Optional[Dict[str, Any]]]: ...

    def _handle_profile_changes(  # noqa: E704
        self, current_profile: Dict[str, Any]
    ) -> Coroutine[Any, Any, None]: ...

    def _detect_profile_changes(  # noqa: E704
        self, old_profile: Dict[str, Any], new_profile: Dict[str, Any]
    ) -> str: ...

    def _format_user_profile_for_context(self, user_profile: Dict[str, Any]) -> str: ...  # noqa: E704
