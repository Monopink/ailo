import aiohttp
import json
import logging
from typing import Optional
from .base import BaseLLM

logger = logging.getLogger(__name__)

class DoubaoLLM(BaseLLM):
    def __init__(self, api_key: str, api_url: Optional[str] = None):
        """
        初始化豆包API客户端
        Args:
            api_key: 豆包API密钥
            api_url: 可选的API地址
        """
        self.api_key = api_key
        self.api_url = api_url or "https://api.doubao.com/v1/chat/completions"  # 示例URL，需要替换为实际的豆包API地址
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def generate_response(self, prompt: str) -> str:
        """
        调用豆包API生成响应
        Args:
            prompt: 输入的提示词
        Returns:
            str: 豆包API的响应
        """
        try:
            payload = {
                "messages": [{"role": "user", "content": prompt}],
                "model": "doubao-chat",  # 需要替换为实际的模型名称
                "temperature": 0.7,
                "max_tokens": 1000
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Doubao API error: {error_text}")
                        return f"API调用失败: {response.status}"

                    result = await response.json()
                    if not result.get("choices"):
                        logger.error(f"Unexpected API response: {result}")
                        return "API返回格式错误"

                    return self.format_response(result["choices"][0]["message"]["content"])

        except aiohttp.ClientError as e:
            logger.error(f"Network error when calling Doubao API: {str(e)}")
            return f"网络请求错误: {str(e)}"
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Doubao API response: {str(e)}")
            return "API响应解析失败"
        except Exception as e:
            logger.error(f"Unexpected error when calling Doubao API: {str(e)}")
            return f"未预期的错误: {str(e)}"

    async def validate_response(self, response: str) -> bool:
        """
        验证豆包API的响应是否有效
        Args:
            response: API响应内容
        Returns:
            bool: 响应是否有效
        """
        return bool(response and not response.startswith(("API调用失败", "网络请求错误", "API响应解析失败", "未预期的错误")))
