import logging
import copy
from typing import Dict, Any, Optional
from volcenginesdkarkruntime import Ark
from .base import BaseLLM

logger = logging.getLogger(__name__)


class Doubao(BaseLLM):
    def __init__(self, api_key: str, model_id: str, base_url: Optional[str] = None):
        """
        初始化豆包API客户端
        Args:
            api_key: 豆包API密钥
            model_id: 模型ID
            base_url: API基础URL，可选
        """
        super().__init__()
        self.model_id = model_id
        self.base_url = base_url or "https://ark.cn-beijing.volces.com/api/v3"
        self.client = Ark(base_url=self.base_url, api_key=api_key)
        # 仅在API调用时使用加密，不影响存储
        self.api_headers = {"x-is-encrypted": "true"}

    async def generate_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成响应，确保存储前解密内容"""
        logger.info("Generating response with context: %s", context)
        try:
            messages = context.get("messages", [])
            if not messages:
                logger.warning("Messages list is empty")
                raise ValueError("Messages list is empty")

            # 创建消息的深拷贝用于加密
            messages_for_api = copy.deepcopy(messages)

            # API调用时使用加密的消息副本
            completion = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages_for_api,
                extra_headers=self.api_headers,
            )

            # 确保存储解密后的内容
            logger.info("Response generated successfully")
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": completion.choices[
                                0
                            ].message.content,  # SDK自动解密
                        }
                    }
                ]
            }

        except Exception as e:
            logger.error(f"Error calling Doubao API: {str(e)}", exc_info=True)
            raise

    async def validate_response(self, response: Dict) -> tuple[bool, Optional[str]]:
        logger.info("Validating response: %s", response)
        try:
            if not isinstance(response, dict):
                logger.warning("Response is not a dictionary")
                return False, "Response is not a dictionary"

            if "choices" not in response:
                logger.warning("Response missing 'choices' field")
                return False, "Response missing 'choices' field"

            choices = response["choices"]
            if not choices or not isinstance(choices, list):
                logger.warning("Invalid or empty choices list")
                return False, "Invalid or empty choices list"

            first_choice = choices[0]
            if "message" not in first_choice and "delta" not in first_choice:
                logger.warning("Choice missing both 'message' and 'delta' fields")
                return False, "Choice missing both 'message' and 'delta' fields"

            logger.info("Response validation successful")
            return True, None

        except Exception as e:
            logger.error(f"Validation error: {str(e)}", exc_info=True)
            return False, f"Validation error: {str(e)}"
