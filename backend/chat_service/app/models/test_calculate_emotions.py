import sys
import os
import json
from datetime import datetime, timedelta, timezone

# ruff: noqa: E402

# prevent generating __pycache__ files
sys.dont_write_bytecode = True

# Add the parent directory to the Python path to allow importing 'enums'.
# This is necessary because relationship_parts.py, which we are testing, depends on it.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Now import relationship_parts after modifying sys.path
from backend.chat_service.app.models.model_ailo_mixins.relationship_mixin import (  # noqa: E402
    ensure_datetime,
    get_passive_score_change,
    calculate_passive_scores,
    refresh_relationship,
    get_level_from_score,
    get_level_by_name,
    apply_buffer,
)


# Mock for the logger, to simulate structlog without importing it.
# The functions in relationship_parts.py expect a logger with this interface.
class MockLogger:
    """A mock logger to print log messages to the console."""

    def _log(self, log_level: str, event: str, **kwargs):
        """Helper to format and print logs."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        details = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        print(f"{timestamp} [{log_level.upper():<7}] {event} " + (f"| {details}" if details else ""))

    def debug(self, event, **kwargs):
        self._log("debug", event, **kwargs)

    def info(self, event, **kwargs):
        self._log("info", event, **kwargs)

    def warning(self, event, **kwargs):
        self._log("warning", event, **kwargs)

    def error(self, event, **kwargs):
        self._log("error", event, **kwargs)


class MockBot:
    """A mock bot object to simulate the bot instance."""

    def __init__(
        self,
        bot_id,
        entity_id,
        last_chat_time,
        friend_config,
        romance_config,
        override_config,
        emotions_config,
        friend_score,
        romance_score,
        self_friend_score,
        self_romance_score,
        friend_score_peak,
        friend_score_trough,
        romance_score_peak,
        relationship_type,
        relationship_level,
        relationship_style,
        friend_level,
        romance_level,
        friend_buffer_status,
        romance_buffer_status,
        is_polite,
        is_crushing,
    ):
        self.id = bot_id
        self.entity_id = entity_id
        self.last_chat_time = last_chat_time
        self.friend_config = friend_config
        self.romance_config = romance_config
        self.override_config = override_config
        self.emotions_config = emotions_config
        self.friend_score = friend_score
        self.romance_score = romance_score
        self.self_friend_score = self_friend_score
        self.self_romance_score = self_romance_score
        self.friend_score_peak = friend_score_peak
        self.friend_score_trough = friend_score_trough
        self.romance_score_peak = romance_score_peak
        self.relationship_type = relationship_type
        self.relationship_level = relationship_level
        self.relationship_style = relationship_style
        self.friend_level = friend_level
        self.romance_level = romance_level
        self.friend_buffer_status = friend_buffer_status
        self.romance_buffer_status = romance_buffer_status
        self.is_polite = is_polite
        self.is_crushing = is_crushing


class TestModel:
    """A test model to provide the necessary environment for the calculation functions."""

    # Bind methods from external module
    _ensure_datetime = ensure_datetime
    _get_level_from_score = get_level_from_score
    _get_level_by_name = get_level_by_name
    _apply_buffer = apply_buffer
    _get_passive_score_change = get_passive_score_change
    _calculate_passive_scores = calculate_passive_scores
    _refresh_relationship = refresh_relationship

    def __init__(self, bot, emotions, state):
        self.logger = MockLogger()
        self.bot = bot
        self.emotions = emotions
        # Unpack state from bot object, similar to ModelAilo
        self.friend_score = getattr(bot, "self_friend_score", 0)
        self.romance_score = getattr(bot, "self_romance_score", 0)
        self.relationship_type = getattr(bot, "relationship_type", "friend")
        self.relationship_level = getattr(bot, "relationship_level", "neutral")
        self.friend_level = getattr(bot, "friend_level", "neutral")
        self.romance_level = getattr(bot, "romance_level", None)
        self.friend_buffer_status = getattr(bot, "friend_buffer_status", "none")
        self.romance_buffer_status = getattr(bot, "romance_buffer_status", "none")
        self.relationship_style = getattr(bot, "relationship_style", "")
        self.is_polite = getattr(bot, "is_polite", False)
        self.is_crushing = getattr(bot, "is_crushing", False)
        self.last_chat_time = getattr(bot, "last_chat_time", None)

        # Get peak/trough from bot and update, similar to ModelAilo
        self.friend_score_peak = max(getattr(bot, "friend_score_peak", 0), self.friend_score)
        self.friend_score_trough = min(getattr(bot, "friend_score_trough", 5000), self.friend_score)
        self.romance_score_peak = max(getattr(bot, "romance_score_peak", 0), self.romance_score)

        # Configs required by calculation functions, passed via state for testing
        self.friend_passive_ratio = state.get("friend_passive_ratio", 0.4)
        self.romance_passive_ratio = state.get("romance_passive_ratio", 0.3)
        self.friend_level_up_buffer = state.get("friend_level_up_buffer", 1.1)
        self.friend_level_down_buffer = state.get("friend_level_down_buffer", 0.92)
        self.romance_level_up_buffer = state.get("romance_level_up_buffer", 1.1)
        self.romance_level_down_buffer = state.get("romance_level_down_buffer", 0.92)

        self.emotion_calculation_rules = {
            "anger": {
                "decay_ratios": {1: 0.5, 2: 0.4, 3: 0.2},
                "duration_multipliers": {1: 10, 2: 180, 3: 840},
                "score_multipliers": {1: 2, 2: 2, 3: 10},
                "duration_random_range": (0.9, 1.1),
            },
        }
        self.passive_score_config = state.get("passive_score_config")

        # Runtime state
        self.is_awake = state.get("is_awake")

        # Initialize calculated scores to the base scores
        self.friend_score_calc = self.friend_score
        self.romance_score_calc = self.romance_score


def run_test(scenario_name, bot_config, test_config, emotions_data):
    """Runs a single test scenario and prints the results."""
    print(f"--- Running Test Scenario: {scenario_name} ---")

    # --- 1. SETUP ---
    mock_bot = MockBot(**bot_config)
    test_model = TestModel(bot=mock_bot, emotions=emotions_data, state=test_config)

    print("Initial Bot Config:")
    print(json.dumps(bot_config, indent=2, default=str, ensure_ascii=False))
    print("Initial Emotions:")
    print(json.dumps(emotions_data, indent=2, ensure_ascii=False))
    print("-" * 20)

    # --- 2. RUN CALCULATION & REFRESH RELATIONSHIP ---
    print("Running calculations...")
    test_model._calculate_passive_scores()
    test_model._refresh_relationship()
    print("...finished.")
    print("-" * 20)

    # --- 3. SHOW RESULTS ---
    final_state = {
        "friend_score": test_model.friend_score,
        "romance_score": test_model.romance_score,
        "friend_score_calc": test_model.friend_score_calc,
        "romance_score_calc": test_model.romance_score_calc,
        "relationship_type": test_model.relationship_type,
        "relationship_level": test_model.relationship_level,
        "friend_level": test_model.friend_level,
        "romance_level": test_model.romance_level,
        "friend_buffer_status": test_model.friend_buffer_status,
        "romance_buffer_status": test_model.romance_buffer_status,
        "relationship_style": test_model.relationship_style,
        "is_polite": test_model.is_polite,
        "is_crushing": test_model.is_crushing,
        "friend_score_peak": test_model.friend_score_peak,
        "friend_score_trough": test_model.friend_score_trough,
        "romance_score_peak": test_model.romance_score_peak,
    }
    print("--- Results ---")
    print("Final State:")
    print(json.dumps(final_state, indent=2, default=str, ensure_ascii=False))
    print("Final Emotions:")
    print(json.dumps(test_model.emotions, indent=2, default=str, ensure_ascii=False))
    print("--------------------------\n")


if __name__ == "__main__":
    now = datetime.now(timezone.utc)

    # --- Common Configurations ---
    FRIEND_CONFIG = [
        {"threshold": 0, "priority": 10, "level": "hostile", "style": "敌对"},
        {"threshold": 100, "priority": 10, "level": "cold", "style": "冷淡"},
        {"threshold": 200, "priority": 10, "level": "neutral", "style": "中立"},
        {"threshold": 300, "priority": 10, "level": "friendly", "style": "友好"},
        {"threshold": 400, "priority": 10, "level": "warm", "style": "温暖"},
    ]
    ROMANCE_CONFIG = [
        {"threshold": 300, "priority": 20, "level": "intimate", "style": "暧昧"},
        {"threshold": 400, "priority": 20, "level": "romantic", "style": "浪漫"},
    ]
    OVERRIDE_CONFIG = {
        "neutral": {
            "type": "friend",
            "override_level": "polite",
            "set_flag": "is_polite",
            "style": "你和user保持礼貌的距离。",
        },
        "intimate": {
            "type": "romance",
            "override_level": "crushing",
            "set_flag": "is_crushing",
            "style": "你暗恋user，但不敢表达。",
        },
    }
    EMOTIONS_CONFIG = {"anger": {"thresholds": {"1": 1, "2": 4, "3": 10}}}
    PASSIVE_SCORE_CONFIG = {
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

    # --- Scenario 1: Active Anger Emotion and Level Up with Buffer ---
    start_time_1 = now - timedelta(minutes=30)
    end_time_1 = start_time_1 + timedelta(hours=1)

    bot_config_1 = {
        "bot_id": 1,
        "entity_id": "b9001",
        "last_chat_time": "2025-03-14T07:47:16.095350+00:00",
        "friend_config": FRIEND_CONFIG,
        "romance_config": ROMANCE_CONFIG,
        "override_config": OVERRIDE_CONFIG,
        "emotions_config": EMOTIONS_CONFIG,
        "friend_score": 200,  # Starts near the 300 threshold
        "romance_score": 0,
        "self_friend_score": 200,
        "self_romance_score": 0,
        "friend_score_peak": 290,
        "friend_score_trough": 290,
        "romance_score_peak": 50,
        "relationship_type": "friend",
        "relationship_level": "cold",
        "friend_level": "cold",
        "romance_level": None,
        "friend_buffer_status": "none",
        "romance_buffer_status": "none",
        "relationship_style": "冷淡",
        "is_polite": True,
        "is_crushing": False,
    }
    test_config_1 = {
        "passive_score_config": PASSIVE_SCORE_CONFIG,
        "is_awake": True,
        "friend_level_up_buffer": 1.1,  # require 300 * 1.1 = 330 to level up
    }
    emotions_1 = {}  # No active emotions, just passive change and buffer check

    run_test("No1 Bot - Level Up Buffer", bot_config_1, test_config_1, emotions_1)

    # --- Scenario 2: Passive Decay ---
    start_time_2 = now - timedelta(days=10)

    bot_config_2 = {
        "bot_id": 2,
        "entity_id": "b9002",
        "last_chat_time": "2025-05-10T07:47:16.095350+00:00",
        "friend_config": FRIEND_CONFIG,
        "romance_config": ROMANCE_CONFIG,
        "override_config": OVERRIDE_CONFIG,
        "emotions_config": EMOTIONS_CONFIG,
        "friend_score": 390,  # High score to test decay
        "romance_score": 200,
        "self_friend_score": 390,
        "self_romance_score": 200,
        "friend_score_peak": 450,
        "friend_score_trough": 100,
        "romance_score_peak": 200,
        "relationship_type": "friend",
        "relationship_level": "warm",
        "friend_level": "warm",
        "romance_level": None,
        "friend_buffer_status": "level_down_buffer",
        "romance_buffer_status": "none",
        "relationship_style": "温暖",
        "is_polite": True,
        "is_crushing": False,
    }
    test_config_2 = {
        "passive_score_config": PASSIVE_SCORE_CONFIG,
        "is_awake": True,
        "friend_passive_ratio": 0.4,  # 450 * 0.4 = 180
    }
    emotions_2 = {
        "anger": {
            "emotion_score": 2,
            "original_emotion_score": 2,
            "emotion_level": 1,
            "friend_score_delta": -50,
            "original_friend_score_delta": -50,
            "romance_score_delta": 0,
            "original_romance_score_delta": 0,
            "decay_ratio": 0.8,
            "start_time": "2025-05-14T07:47:16.095350+00:00",
            "end_time": "2025-05-16T07:47:16.095350+00:00",
            "original_end_time": "2025-05-14T07:47:16.095350+00:00",
            "is_ended": False,
            "update_time": now.isoformat(),
        }
    }

    run_test("No2 Bot - Passive Decay", bot_config_2, test_config_2, emotions_2)

    # # --- Scenario 3: Level Down with Buffer ---
    # bot_config_3 = {
    #     "bot_id": 3,
    #     "entity_id": "b9003",
    #     "last_chat_time": "2025-05-14T07:47:16.095350+00:00",
    #     "friend_config": FRIEND_CONFIG,
    #     "romance_config": ROMANCE_CONFIG,
    #     "override_config": OVERRIDE_CONFIG,
    #     "emotions_config": EMOTIONS_CONFIG,
    #     "friend_score": 305,  # Just above the 300 threshold for friendly
    #     "romance_score": 0,
    #     "self_friend_score": 305,
    #     "self_romance_score": 0,
    #     "friend_score_peak": 305,
    #     "friend_score_trough": 305,
    #     "romance_score_peak": 0,
    #     "relationship_type": "friend",
    #     "relationship_level": "friendly",
    #     "friend_level": "friendly",
    #     "romance_level": None,
    #     "friend_buffer_status": "none",
    #     "romance_buffer_status": "none",
    #     "relationship_style": "友好",
    #     "is_polite": False,
    #     "is_crushing": False,
    # }
    # test_config_3 = {
    #     "passive_score_config": PASSIVE_SCORE_CONFIG,
    #     "is_awake": True,
    #     "friend_level_down_buffer": 0.92,  # must be below 300 * 0.92 = 276 to level down
    # }
    # # This response will lower the score
    # emotions_3 = {
    #     "anger": {
    #         "emotion_score": 2,
    #         "original_emotion_score": 2,
    #         "emotion_level": 1,
    #         "friend_score_delta": -20,
    #         "original_friend_score_delta": -20,
    #         "romance_score_delta": 0,
    #         "original_romance_score_delta": 0,
    #         "decay_ratio": 0.8,
    #         "start_time": "2025-05-14T07:47:16.095350+00:00",
    #         "end_time": "2025-05-16T07:47:16.095350+00:00",
    #         "original_end_time": "2025-05-14T07:47:16.095350+00:00",
    #         "is_ended": False,
    #         "update_time": now.isoformat(),
    #     }
    # }

    # run_test("No3 Bot - Level Down Buffer", bot_config_3, test_config_3, emotions_3)
