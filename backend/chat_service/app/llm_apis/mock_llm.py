import asyncio
import random
import time
import logging
from typing import Dict, Any, List, Optional
from .base import BaseLLM

logger = logging.getLogger(__name__)


class MockLLM(BaseLLM):
    async def generate_response(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """

        模拟大模型API响应
        Args:
            request: 包含messages等参数的请求字典
        Returns:
            Dict: 模拟的API响应
        """
        try:
            logger.info(f"Received request: {request}")

            # 验证请求参数
            messages: List[Dict[str, str]] = request.get("messages", [])
            if not messages:
                error_msg = "Messages cannot be empty"
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.debug(f"Processing messages: {messages}")
            logger.debug(
                f"Request parameters: temperature={request.get('temperature')}, "
                f"max_tokens={request.get('max_tokens')}, "
                f"top_p={request.get('top_p')}"
            )

            # 模拟 API 调用延迟
            delay = random.uniform(0.5, 2.0)
            logger.debug(f"Simulating API delay: {delay:.2f} seconds")
            await asyncio.sleep(delay)

            # 生成模拟回复内容
            response_content = self._generate_mock_content(messages[-1]["content"])
            logger.debug(f"Generated response content: {response_content}")

            # 构造标准响应格式
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

            logger.info(f"Generated response: {response}")
            return response

        except Exception as e:
            error_response = {
                "error": {
                    "message": f"Error generating response: {str(e)}",
                    "type": "mock_api_error",
                    "code": 500,
                }
            }
            logger.error(f"Error in generate_response: {str(e)}", exc_info=True)
            logger.error(f"Returning error response: {error_response}")
            return error_response

    def _generate_mock_content(self, prompt: str) -> str:
        """
        生成模拟回复内容
        """
        logger.debug(f"Generating mock content for prompt: {prompt}")

        # 简单的回复生成逻辑
        keywords = ["有趣", "理解", "建议", "想法", "感觉", "希望", "开心", "思考"]
        responses = [
            f"我{random.choice(keywords)}你说的内容。",
            f"这确实是个值得{random.choice(keywords)}的话题。",
            f"听你这么说，我也有了新的{random.choice(keywords)}。",
            f"我们可以一起{random.choice(keywords)}这个问题。",
        ]

        response = random.choice(responses)
        logger.debug(f"Generated mock content: {response}")
        return response

    async def validate_response(
        self, response: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        验证响应是否符合标准LLM响应结构

        Args:
            response: LLM响应内容

        Returns:
            tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        if "error" in response:
            error_msg = f"API error: {response['error']}"
            return False, error_msg

        try:
            required_fields = ["id", "object", "created", "model", "choices", "usage"]
            missing_fields = [
                field for field in required_fields if field not in response
            ]
            if missing_fields:
                return False, f"Missing required fields: {missing_fields}"

            if not response["choices"] or not isinstance(response["choices"], list):
                return False, "Invalid or empty choices field"

            choice = response["choices"][0]
            if not all(key in choice["message"] for key in ["role", "content"]):
                return False, "Invalid message format in choice"

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"
