import asyncio
import random
import time
import logging
from typing import Dict, Any, List
from .base import BaseLLMAPI

logger = logging.getLogger(__name__)

class MockLLMAPI(BaseLLMAPI):
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
            messages: List[Dict[str, str]] = request.get('messages', [])
            if not messages:
                error_msg = "Messages cannot be empty"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.debug(f"Processing messages: {messages}")
            logger.debug(f"Request parameters: temperature={request.get('temperature')}, "
                        f"max_tokens={request.get('max_tokens')}, "
                        f"top_p={request.get('top_p')}")

            # 模拟 API 调用延迟
            delay = random.uniform(0.5, 2.0)
            logger.debug(f"Simulating API delay: {delay:.2f} seconds")
            await asyncio.sleep(delay)
            
            # 生成模拟回复内容
            response_content = self._generate_mock_content(messages[-1]['content'])
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
                    "total_tokens": (len(str(messages)) + len(response_content)) // 4
                },
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": response_content
                        },
                        "finish_reason": "stop",
                        "index": 0
                    }
                ]
            }
            
            logger.info(f"Generated response: {response}")
            return response

        except Exception as e:
            error_response = {
                "error": {
                    "message": f"Error generating response: {str(e)}",
                    "type": "mock_api_error",
                    "code": 500
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
            f"我们可以一起{random.choice(keywords)}这个问题。"
        ]
        
        response = random.choice(responses)
        logger.debug(f"Generated mock content: {response}")
        return response

    async def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        验证响应是否合适
        """
        logger.debug(f"Validating response: {response}")
        
        if "error" in response:
            logger.error(f"Response contains error: {response['error']}")
            return False
            
        try:
            choices = response.get("choices", [])
            if not choices:
                logger.error("Response contains no choices")
                return False
                
            content = choices[0].get("message", {}).get("content", "")
            if not content:
                logger.error("Response content is empty")
                return False
            
            logger.debug("Response validation successful")
            return True
            
        except Exception as e:
            logger.error(f"Error during response validation: {str(e)}", exc_info=True)
            return False