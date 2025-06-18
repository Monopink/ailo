import asyncio
import random
import time
from typing import Dict, Any, List, Optional
from .base import BaseLLM
from utils.logging import get_logger

logger = get_logger("says.llm_apis.mock_llm")


class MockLLM(BaseLLM):
    async def generate_response(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mock LLM API response
        Args:
            request: Request dictionary containing messages and other parameters
        Returns:
            Dict: Mocked API response
        """
        try:
            logger.debug("received_request", request=request)

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

            # Simulate API call delay
            delay = random.uniform(0.5, 2.0)
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

    def _generate_mock_content(self, prompt: str) -> str:
        """
        Generate mock response content
        """
        logger.info("generating_mock_content", prompt=prompt)

        # Simple response generation logic
        keywords = ["有趣", "理解", "建议", "想法", "感觉", "希望", "开心", "思考"]
        responses = [
            f"我{random.choice(keywords)}你说的内容。",
            f"这确实是个值得{random.choice(keywords)}的话题。",
            f"听你这么说，我也有了新的{random.choice(keywords)}。",
            f"我们可以一起{random.choice(keywords)}这个问题。",
        ]

        response = random.choice(responses)
        logger.info("generated_mock_content", content=response)
        return response

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
