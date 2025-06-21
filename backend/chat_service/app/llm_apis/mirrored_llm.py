import json
import time
import random
from typing import Dict, Any, Optional
from .base import BaseLLM
from utils.logging import get_logger

logger = get_logger("says.llm_apis.mirrored_llm")


class MirroredLLM(BaseLLM):
    async def generate_response(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Serialize received context into standard LLM response structure
        Args:
            context: Context dictionary
            **kwargs: Additional keyword arguments (ignored in this implementation)
        Returns:
            Dict: Standardized LLM response structure
        """
        try:
            logger.info("received_context", kwargs_keys=list(kwargs.keys()) if kwargs else [])

            # Serialize context to JSON string, ensuring proper Unicode handling
            serialized_content = json.dumps(context, ensure_ascii=False)

            # Construct standard LLM response structure
            response = {
                "id": f"mirror-{random.randint(1000000, 9999999)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "mirrored-llm",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": serialized_content},
                        "logprobs": None,
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": len(str(context)) // 4,
                    "completion_tokens": len(serialized_content) // 4,
                    "total_tokens": (len(str(context)) + len(serialized_content)) // 4,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            }

            return response

        except Exception as e:
            logger.error("generate_response_error", error=str(e))
            # Return error response instead of None
            return {"error": {"message": str(e), "type": "internal_error", "code": 500}}

    async def validate_response(self, response: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate if response matches standard LLM response structure

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

            logger.info("response_validation_successful")
            return True, None

        except Exception as e:
            logger.error("validation_error", error=str(e))
            return False, f"Validation error: {str(e)}"
