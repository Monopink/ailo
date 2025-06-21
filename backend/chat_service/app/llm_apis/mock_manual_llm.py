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
                    "thinking": "这是一个普通的问候，对方看起来是想开始一段对话。天气确实不错，可以用这个话题开场。我和对方的关系还不错，可以轻松友好一点。",
                    "is_attack": False,
                    "response": True,
                    "content": "你好啊，今天天气真不错！",
                    "emotions": {"anger": 5},
                    "friend_score": 1,
                    "romance_score": 0,
                    "is_important": True,
                    "note": "对方主动打招呼，我回应了一下",
                    "next_message": "",
                    "block": False,
                },
                ensure_ascii=False,
            ),
            # Response 2
            json.dumps(
                {
                    "thinking": "我现在比较忙，没有太多时间聊天。虽然不想完全不理对方，但也只能简单回复一下，告诉对方我现在不太方便。",
                    "is_attack": False,
                    "response": True,
                    "content": "嗯...我正在忙，等会再聊吧。",
                    "emotions": {"none": 0},
                    "friend_score": 0,
                    "romance_score": 0,
                    "is_important": False,
                    "note": "我现在在忙，没空聊天",
                    "next_message": "忙完了，你之前想聊什么？",
                    "block": False,
                },
                ensure_ascii=False,
            ),
            # Response 3
            json.dumps(
                {
                    "thinking": "对方的消息有些模糊，我没完全理解是什么意思。最好请对方澄清一下，避免误解。我对这个话题也不是特别感兴趣。",
                    "is_attack": False,
                    "response": True,
                    "content": "你说什么？我没听清楚。",
                    "emotions": {"none": 0},
                    "friend_score": 0,
                    "romance_score": 0,
                    "is_important": False,
                    "note": "没理解对方的意思",
                    "next_message": "",
                    "block": False,
                },
                ensure_ascii=False,
            ),
        ]
        logger.info("responses_loaded", count=len(self.RESPONSES))

    async def generate_response(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Return the next predefined response from the hardcoded responses.

        Args:
            context: Context dictionary (ignored in this implementation)
            **kwargs: Additional arguments (ignored in this implementation but accepted for compatibility)

        Returns:
            Dict: A properly formatted LLM response
        """
        # Log the arguments for debugging
        logger.info(
            "generate_response_called",
            context_keys=list(context.keys()),
            kwargs_keys=list(kwargs.keys()) if kwargs else [],
        )

        # Small delay to simulate API call
        await asyncio.sleep(0.2)

        # Get next response from the queue
        if not self.RESPONSES:
            logger.warning("no_responses_configured_using_default")
            content = json.dumps(
                {
                    "thinking": "这是一个默认回复。我不确定对方想表达什么，所以给出一个通用的回应。",
                    "is_attack": False,
                    "response": True,
                    "content": "默认回复",
                    "emotions": {"none": 0},
                    "friend_score": 0,
                    "romance_score": 0,
                    "is_important": False,
                    "note": "使用了默认回复",
                    "next_message": "",
                    "block": False,
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
