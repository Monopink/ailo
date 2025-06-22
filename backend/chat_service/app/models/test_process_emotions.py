import sys
import os
import json
from datetime import datetime, timezone

# prevent generating __pycache__ files
sys.dont_write_bytecode = True

# Add the parent directory to the Python path to allow importing 'enums'.
# This is necessary because relationship_parts.py, which we are testing, depends on it.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Assuming this script is in the same directory as relationship_parts.py
# If not, you might need to adjust the import path
try:
    from relationship_parts import process_emotions_and_score, ensure_datetime, new_anger_emotion
except ImportError:
    print("Error: Make sure 'test_process_emotions.py' is in the same directory as 'relationship_parts.py'")
    exit(1)

# --- Mock Objects ---


# Mock for Enums, to avoid external imports.
# This is necessary because relationship_parts.py uses them.
class EmotionType:
    """Mock for EmotionType enum
    In the real enums.py, EmotionType is defined as:
    class EmotionType(enum.Enum):
        ANGER = "anger"
        MOVED = "moved"
    """

    class ANGER:
        value = "anger"  # Enum value
        name = "ANGER"  # Enum member name

    class MOVED:
        value = "moved"  # Enum value
        name = "MOVED"  # Enum member name


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


# A simple class to simulate the 'bot' object required by the function
class MockBot:
    """Simulates the bot object with necessary configurations."""

    def __init__(self):
        self.id = "b9001-test"
        # Configuration for emotion thresholds (e.g., anger levels)
        self.emotions_config = {
            "anger": {"thresholds": {1: 1, 2: 4, 3: 10}},
        }
        # A constant used in duration calculation
        self.friend_score_neg_k = 120


class MockModelLily:
    """
    Simulates the main model instance ('self') that process_emotions expects.
    It holds the state (like current emotions) and necessary configurations.
    """

    # The function needs a way to handle datetime strings
    _ensure_datetime = ensure_datetime
    _new_anger_emotion = new_anger_emotion

    def __init__(self):
        # Assign the mock logger
        self.logger = MockLogger()
        self.bot = MockBot()
        # You can pre-populate 'emotions' to test updates on existing data.
        # Example: To test a decrease in anger, you could uncomment the following block.

        # now = datetime.now(timezone.utc)
        # self.emotions = {
        #     "anger": {
        #         "emotion_score": 5,
        #         "original_emotion_score": 10,
        #         "emotion_level": 2,
        #         "friend_score_delta": -50,
        #         "original_friend_score_delta": -100,
        #         "romance_score_delta": -50,
        #         "original_romance_score_delta": -100,
        #         "decay_ratio": 0.4,
        #         "start_time": "2025-06-16T20:41:44.590823+00:00",
        #         "end_time": "2025-06-16T20:41:44.590823+00:00",
        #         "original_end_time": "2025-06-16T20:41:44.590823+00:00",
        #         "is_ended": False,
        #         "update_time": now.isoformat(),
        #     }
        # }
        self.emotions = {}
        self.friend_score = 1687
        self.romance_score = 100
        # self.emotions = {}  # Start with no emotions for a clean test

        # Emotion calculation rules, copied from ModelLily
        self.emotion_calculation_rules = {
            "anger": {
                "decay_ratios": {1: 0.5, 2: 0.4, 3: 0.2},
                "duration_multipliers": {1: 10, 2: 180, 3: 840},
                "score_multipliers": {1: 2, 2: 2, 3: 10},
                "duration_random_range": (0.9, 1.1),
            },
        }

    def run_process_emotions(self, response_result: dict):
        """
        A helper method to call the standalone process_emotions function,
        passing this instance as 'self'.
        """
        process_emotions_and_score(self, response_result)


# --- Test Execution ---
def run_test():
    """
    Main function to run the test.
    You can modify the 'response_result' dictionary and the initial
    state of 'lily_instance.emotions' to test different scenarios.
    """
    print("--- Starting emotion processing test ---")

    # 1. Initialize the mock model instance
    lily_instance = MockModelLily()

    # 2. ***** EDIT HERE TO TEST *****
    # This dictionary simulates the response from the LLM.
    # Modify the values to test different scenarios.
    response_result = {
        "emotions": {
            "anger": 12  # <-- CHANGE THIS: Anger score from LLM (1-12). Use 0 or remove to test no-anger.
        },
        "friend_score": -5,  # <-- CHANGE THIS: Negative impact on friendship (-5 to 5).
        "romance_score": -1,  # <-- CHANGE THIS: Negative impact on romance (-5 to 5).
        "content": "This is some response content from the LLM.",
    }

    print("\n[State Before]")
    print(f"Initial emotions: {json.dumps(lily_instance.emotions, indent=2, ensure_ascii=False)}")
    print(f"Input response: {json.dumps(response_result, indent=2, ensure_ascii=False)}")

    # 3. Call the function to be tested
    lily_instance.run_process_emotions(response_result)

    print("\n[State After]")
    print(f"Updated emotions: {json.dumps(lily_instance.emotions, indent=2, ensure_ascii=False)}")

    print("\n--- Test finished ---")


if __name__ == "__main__":
    run_test()
