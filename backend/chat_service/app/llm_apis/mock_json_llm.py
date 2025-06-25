import asyncio
import random
import time
import json
from typing import Dict, Any, List, Optional, Union, TypedDict, Tuple
from enum import Enum
from .base import BaseLLM
from ..utils.logging import get_logger

logger = get_logger("says.llm_apis.mock_json_llm")


class MockMode(Enum):
    """Mock mode"""

    RANDOM = "random"  # Random fluctuation
    FIXED = "fixed"  # Fixed value


class EmotionsValue(TypedDict):
    """Emotion value type definition"""

    types: List[str]
    scores: Dict[str, int]


class MockConfig:
    """Mock configuration"""

    def __init__(
        self,
        mode: MockMode = MockMode.RANDOM,
        value: Optional[Union[bool, int, EmotionsValue]] = None,
    ):
        self.mode = mode
        self.value = value


class DelayConfig:
    """Delay configuration"""

    def __init__(
        self,
        mode: MockMode = MockMode.RANDOM,
        base_delay: float = 2.0,
        random_range: Tuple[float, float] = (0.5, 1.5),
    ):
        """Initialize delay configuration

        Args:
            mode: Mock mode, RANDOM for random delay, FIXED for fixed delay
            base_delay: Base delay time (seconds)
            random_range: Random delay range multiplier, final delay = base_delay * random_value
                        where random_value is between random_range[0] and random_range[1]
        """
        self.mode = mode
        self.base_delay = base_delay
        self.random_range = random_range

    def get_delay(self) -> float:
        """Get delay time"""
        if self.mode == MockMode.FIXED:
            return self.base_delay
        return self.base_delay * random.uniform(*self.random_range)


class MockJsonLLM(BaseLLM):
    def __init__(self, base_delay: float = 2.0):
        """Initialize mock configuration

        Args:
            base_delay: Base delay time (seconds)
        """
        self.attack_config = MockConfig()
        self.friend_score_config = MockConfig()
        self.romance_score_config = MockConfig()
        self.emotions_config = MockConfig()
        self.delay_config = DelayConfig(base_delay=base_delay)

    def set_attack_mode(self, mode: MockMode, value: Optional[bool] = None) -> None:
        """Set attack detection mode

        Args:
            mode: Mock mode
            value: Fixed value (only used in FIXED mode)
        """
        self.attack_config = MockConfig(mode=mode, value=value)

    def set_friend_score_mode(self, mode: MockMode, value: Optional[int] = None) -> None:
        """Set friendship score mode

        Args:
            mode: Mock mode
            value: Fixed value (only used in FIXED mode)
        """
        self.friend_score_config = MockConfig(mode=mode, value=value)

    def set_romance_score_mode(self, mode: MockMode, value: Optional[int] = None) -> None:
        """Set romance score mode

        Args:
            mode: Mock mode
            value: Fixed value (only used in FIXED mode)
        """
        self.romance_score_config = MockConfig(mode=mode, value=value)

    def set_emotions_mode(
        self,
        mode: MockMode,
        value: Optional[Dict[str, int]] = None,
        types: Optional[List[str]] = None,
    ) -> None:
        """Set emotion mode

        Args:
            mode: Mock mode
            value: Fixed emotion scores (only used in FIXED mode)
            types: Fixed emotion type list (only used in FIXED mode)
        """
        if mode == MockMode.FIXED and value is not None and types is not None:
            emotions_value: EmotionsValue = {"types": types, "scores": value}
            self.emotions_config = MockConfig(mode=mode, value=emotions_value)
        else:
            self.emotions_config = MockConfig(mode=mode)

    def set_delay_config(
        self,
        mode: MockMode,
        base_delay: Optional[float] = None,
        random_range: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Set delay configuration

        Args:
            mode: Mock mode
            base_delay: Base delay time (seconds)
            random_range: Random delay range multiplier
        """
        if base_delay is not None:
            self.delay_config.base_delay = base_delay
        if random_range is not None:
            self.delay_config.random_range = random_range
        self.delay_config.mode = mode

    def _get_attack_check(self) -> bool:
        """Get attack detection result"""
        if (
            self.attack_config.mode == MockMode.FIXED
            and self.attack_config.value is not None
            and isinstance(self.attack_config.value, bool)
        ):
            return self.attack_config.value
        return random.random() < 0.1  # 10% chance for True

    def _get_friend_score(self) -> int:
        """Get friendship score"""
        if (
            self.friend_score_config.mode == MockMode.FIXED
            and self.friend_score_config.value is not None
            and isinstance(self.friend_score_config.value, int)
        ):
            return self.friend_score_config.value
        return random.randint(-5, 5)

    def _get_romance_score(self) -> int:
        """Get romance score"""
        if (
            self.romance_score_config.mode == MockMode.FIXED
            and self.romance_score_config.value is not None
            and isinstance(self.romance_score_config.value, int)
        ):
            return self.romance_score_config.value
        return random.randint(-5, 5)

    def _get_emotions(self) -> Dict[str, int]:
        """Get emotion data"""
        if (
            self.emotions_config.mode == MockMode.FIXED
            and self.emotions_config.value is not None
            and isinstance(self.emotions_config.value, dict)
        ):
            # Convert old EmotionsValue format to new format if needed
            if "types" in self.emotions_config.value and "scores" in self.emotions_config.value:
                types = self.emotions_config.value["types"]
                scores = self.emotions_config.value["scores"]
                if types and scores:
                    # Take only the first emotion type
                    emotion_type = types[0]
                    return {emotion_type: scores.get(emotion_type, 5)}
            else:
                # Already in new format
                return self.emotions_config.value

        # Random mode
        emotion_types = ["anger", "happy", "none"]
        selected_type = random.choice(emotion_types)
        if selected_type == "none":
            return {}
        return {selected_type: random.randint(1, 12)}

    def _generate_mock_content(self, prompt: str) -> str:
        """Generate mock response content, return JSON formatted string"""
        logger.info("generating_mock_content", prompt=prompt)

        # Generate base response content
        responses = [
            "我理解你的想法，让我们继续探讨这个话题。",
            "这是一个很有趣的观点，我很认同。",
            "你说得很有道理，我们可以深入交流。",
            "确实如此，这让我想到了一些新的思路。",
        ]

        # Build new response format
        response_json = {
            "is_attack": self._get_attack_check(),
            "response": True,
            "content": random.choice(responses),
            "emotions": self._get_emotions(),
            "friend_score": self._get_friend_score(),
            "romance_score": self._get_romance_score(),
        }

        # Randomly add summary field (20% chance)
        if random.random() < 0.2:
            response_json["summary"] = "这是一个对话总结示例。"

        # Format JSON string using json.dumps
        response = json.dumps(response_json, ensure_ascii=False)
        logger.info("generated_mock_content", response=response)
        return response

    async def generate_response(self, request: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Mock LLM API response

        Args:
            request: Request dictionary containing messages and other parameters
            **kwargs: Additional keyword arguments (ignored in this implementation)

        Returns:
            Dict: Mocked API response
        """
        try:
            logger.debug("received_request", request=request, kwargs=kwargs)

            # Validate request parameters
            messages: List[Dict[str, str]] = request.get("messages", [])
            if not messages:
                error_msg = "Messages cannot be empty"
                logger.error("empty_messages")
                raise ValueError(error_msg)

            logger.info("processing_messages", messages=messages)
            logger.info(
                "request_parameters",
                temperature=request.get("temperature"),
                max_tokens=request.get("max_tokens"),
                top_p=request.get("top_p"),
            )

            # Get delay time
            delay = self.delay_config.get_delay()
            logger.info("simulating_api_delay", delay=f"{delay:.2f}")
            await asyncio.sleep(delay)

            # Generate mock response content
            response_content = self._generate_mock_content(messages[-1]["content"])
            logger.info("generated_response_content", content=response_content)

            # Construct standard response format
            response = {
                "id": f"mockcmpl-{random.randint(1000000, 9999999)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "mock-gpt",
                "usage": {
                    "prompt_tokens": len(str(messages)) // 4,
                    "completion_tokens": len(response_content) // 4,
                    "total_tokens": (len(str(messages)) + len(response_content)) // 4,
                },
                "choices": [
                    {
                        "message": {"role": "assistant", "content": response_content},
                        "finish_reason": "stop",
                        "index": 0,
                    }
                ],
            }

            logger.info("generated_response", response=response)
            return response

        except Exception as e:
            error_response = {
                "error": {
                    "message": f"Error generating response: {str(e)}",
                    "type": "mock_api_error",
                    "code": 500,
                }
            }
            logger.error("generate_response_error", error=str(e), exc_info=True)
            logger.error("error_response", response=error_response)
            return error_response

    async def validate_response(self, response: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate if response matches standard LLM response structure

        Note: This method only validates the LLM API response structure, not the business logic
        of the response content. Content business logic validation is handled by context_strategy.

        Args:
            response: LLM response content

        Returns:
            tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if "error" in response:
            error_msg = f"API error: {response['error']}"
            return False, error_msg

        try:
            required_fields = ["id", "object", "created", "model", "choices", "usage"]
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                logger.warning("missing_required_fields", fields=missing_fields)
                return False, f"Missing required fields: {missing_fields}"

            if not response["choices"] or not isinstance(response["choices"], list):
                logger.warning("invalid_choices_field")
                return False, "Invalid or empty choices field"

            choice = response["choices"][0]
            if not all(key in choice["message"] for key in ["role", "content"]):
                logger.warning("invalid_message_format")
                return False, "Invalid message format in choice"

            # Check if JSON format is valid
            try:
                json.loads(choice["message"]["content"])
            except json.JSONDecodeError:
                logger.warning("invalid_json_content")
                return False, "Invalid JSON in response content"

            logger.info("response_validation_successful")
            return True, None

        except Exception as e:
            logger.error("validation_error", error=str(e))
            return False, f"Validation error: {str(e)}"
