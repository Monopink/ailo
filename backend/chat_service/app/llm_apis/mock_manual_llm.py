from typing import Dict, Any, Optional
import json
import asyncio
from utils.logging import get_logger

from .base import BaseLLM

logger = get_logger("says.llm_apis.mock_manual_llm")


class MockLLMManual(BaseLLM):
    """
    A manual mock LLM implementation that returns predefined responses in a cycle.
    """

    # Default response structure
    DEFAULT_RESPONSE_TEMPLATE = {
        "id": "mock-response-id",
        "object": "chat.completion",
        "created": 1677858242,
        "model": "mock-manual-model",
        "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
        "choices": [
            {
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "stop",
                "index": 0,
            }
        ],
    }

    def __init__(self):
        """Initialize with hardcoded response queue."""
        super().__init__()
        self._current_index = 0
        logger.info("initialized")

        # HARDCODED RESPONSES - EDIT THESE DIRECTLY
        # All responses must be valid JSON strings matching the model's expected format
        self.RESPONSES = [
            # Response 1
            json.dumps(
                {
                    "is_attack": False,
                    "response": True,
                    "content": "你好啊，今天天气真不错！",
                    "emotions": {"anger": 5},
                    "friend_score": 1,
                    "romance_score": 0,
                    "is_important": True,
                },
                ensure_ascii=False,
            ),
            # Response 2
            json.dumps(
                {
                    "is_attack": False,
                    "response": True,
                    "content": "嗯...我正在忙，等会再聊吧。",
                    "emotions": {"none": 0},
                    "friend_score": 0,
                    "romance_score": 0,
                    "is_important": False,
                },
                ensure_ascii=False,
            ),
            # Response 3
            json.dumps(
                {
                    "is_attack": False,
                    "response": True,
                    "content": "你说什么？我没听清楚。",
                    "emotions": {"none": 0},
                    "friend_score": 0,
                    "romance_score": 0,
                    "is_important": False,
                },
                ensure_ascii=False,
            ),
        ]
        logger.info("responses_loaded", count=len(self.RESPONSES))

    async def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return the next predefined response from the hardcoded responses.

        Args:
            context: Context dictionary (ignored in this implementation)

        Returns:
            Dict: A properly formatted LLM response
        """
        # Small delay to simulate API call
        await asyncio.sleep(0.2)

        # Get next response from the queue
        if not self.RESPONSES:
            logger.warning("no_responses_configured_using_default")
            content = json.dumps(
                {
                    "is_attack": False,
                    "response": True,
                    "content": "默认回复",
                    "emotions": {"none": 0},
                    "friend_score": 0,
                    "romance_score": 0,
                },
                ensure_ascii=False,
            )
        else:
            content = self.RESPONSES[self._current_index]
            logger.info("using_response", index=self._current_index)
            self._current_index = (self._current_index + 1) % len(self.RESPONSES)
            logger.info("next_index_updated", next_index=self._current_index)

        # Create response structure
        response = self.DEFAULT_RESPONSE_TEMPLATE.copy()
        response["choices"][0]["message"]["content"] = content

        logger.info("response_generated")
        return response

    async def validate_response(self, response: Dict) -> tuple[bool, Optional[str]]:
        """
        Validate the response structure.

        Args:
            response: The response to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        if not isinstance(response, dict):
            logger.error("validation_failed", reason="not_a_dictionary")
            return False, "Response is not a dictionary"

        if "choices" not in response:
            logger.error("validation_failed", reason="missing_choices_field")
            return False, "Response missing 'choices' field"

        if not response["choices"] or not isinstance(response["choices"], list):
            logger.error("validation_failed", reason="invalid_choices_field")
            return False, "Response has invalid 'choices' field"

        if "message" not in response["choices"][0]:
            logger.error("validation_failed", reason="missing_message_in_first_choice")
            return False, "Response missing 'message' in first choice"

        if "content" not in response["choices"][0]["message"]:
            logger.error("validation_failed", reason="missing_content_in_message")
            return False, "Response missing 'content' in first choice message"

        # Basic JSON validation of content
        try:
            content = response["choices"][0]["message"]["content"]
            json.loads(content)
        except json.JSONDecodeError:
            logger.error("validation_failed", reason="invalid_json_content")
            return False, "Response content is not valid JSON"

        logger.info("validation_successful")
        return True, None
