import asyncio
import random
import time
import logging
import json
from typing import Dict, Any, List, Optional
from .base import BaseLLM

logger = logging.getLogger(__name__)


class MockJsonLLM(BaseLLM):
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
        生成模拟回复内容，返回JSON格式的字符串
        """
        logger.debug(f"Generating mock content for prompt: {prompt}")

        # 基础回复内容生成
        responses = [
            "我理解你的想法，让我们继续探讨这个话题。",
            "这是一个很有趣的观点，我很认同。",
            "你说得很有道理，我们可以深入交流。",
            "确实如此，这让我想到了一些新的思路。",
        ]

        # 随机生成情感相关参数
        emotion_types = ["开心", "平静", "思考", "困惑", "兴奋"]
        feelings_classes = ["积极", "中性", "消极"]

        response_json = {
            "response": True,
            "content": random.choice(responses),
            "feelings_class": random.choice(feelings_classes),
            "feelings_score": random.randint(1, 10),
            "emotion_type": random.choice(emotion_types),
            "intensity": random.randint(0, 100),
            "relationship": random.randint(1, 5),
            "is_attack": random.random() < 0.1,  # 10%概率为True
        }

        # 使用 json.dumps 而不是 str() 来正确格式化 JSON 字符串
        response = json.dumps(response_json, ensure_ascii=False)
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
