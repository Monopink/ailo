import json
import time
import random
from typing import Dict, Any, Optional
from .base import BaseLLM
import logging

logger = logging.getLogger(__name__)


class MirroredLLM(BaseLLM):
    async def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        将收到的context序列化后放入标准LLM响应结构中返回
        Args:
            context: 上下文字典
        Returns:
            Dict: 标准化的LLM响应结构
        """
        try:
            logger.info("MirroredLLM received context")

            # 将context序列化为JSON字符串，确保Unicode字符正确处理
            serialized_content = json.dumps(context, ensure_ascii=False)

            # 构造标准LLM响应结构
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
            logger.error(f"Error in generate_response: {str(e)}")
            # 返回错误响应而不是 None
            return {"error": {"message": str(e), "type": "internal_error", "code": 500}}

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
