import asyncio
import random
import time
import logging
import json
from typing import Dict, Any, List, Optional, Union, TypedDict, Tuple
from enum import Enum
from .base import BaseLLM

logger = logging.getLogger(__name__)


class MockMode(Enum):
    """模拟模式"""

    RANDOM = "random"  # 随机波动
    FIXED = "fixed"  # 固定值


class EmotionsValue(TypedDict):
    """情绪值类型定义"""

    types: List[str]
    scores: Dict[str, int]


class MockConfig:
    """模拟配置"""

    def __init__(
        self,
        mode: MockMode = MockMode.RANDOM,
        value: Optional[Union[bool, int, EmotionsValue]] = None,
    ):
        self.mode = mode
        self.value = value


class DelayConfig:
    """延迟配置"""

    def __init__(
        self,
        mode: MockMode = MockMode.RANDOM,
        base_delay: float = 2.0,
        random_range: Tuple[float, float] = (0.5, 1.5),
    ):
        """初始化延迟配置

        Args:
            mode: 模拟模式，RANDOM 为随机延迟，FIXED 为固定延迟
            base_delay: 基础延迟时间（秒）
            random_range: 随机延迟范围的乘数，最终延迟 = base_delay * random_value
                        其中 random_value 在 random_range[0] 和 random_range[1] 之间
        """
        self.mode = mode
        self.base_delay = base_delay
        self.random_range = random_range

    def get_delay(self) -> float:
        """获取延迟时间"""
        if self.mode == MockMode.FIXED:
            return self.base_delay
        return self.base_delay * random.uniform(*self.random_range)


class MockJsonLLM(BaseLLM):
    def __init__(self, base_delay: float = 2.0):
        """初始化模拟配置

        Args:
            base_delay: 基础延迟时间（秒）
        """
        self.attack_config = MockConfig()
        self.friend_score_config = MockConfig()
        self.romance_score_config = MockConfig()
        self.emotions_config = MockConfig()
        self.delay_config = DelayConfig(base_delay=base_delay)

    def set_attack_mode(self, mode: MockMode, value: Optional[bool] = None) -> None:
        """设置攻击检测模式

        Args:
            mode: 模拟模式
            value: 固定值（仅在 FIXED 模式下使用）
        """
        self.attack_config = MockConfig(mode=mode, value=value)

    def set_friend_score_mode(self, mode: MockMode, value: Optional[int] = None) -> None:
        """设置友情分数模式

        Args:
            mode: 模拟模式
            value: 固定值（仅在 FIXED 模式下使用）
        """
        self.friend_score_config = MockConfig(mode=mode, value=value)

    def set_romance_score_mode(self, mode: MockMode, value: Optional[int] = None) -> None:
        """设置浪漫分数模式

        Args:
            mode: 模拟模式
            value: 固定值（仅在 FIXED 模式下使用）
        """
        self.romance_score_config = MockConfig(mode=mode, value=value)

    def set_emotions_mode(
        self,
        mode: MockMode,
        value: Optional[Dict[str, int]] = None,
        types: Optional[List[str]] = None,
    ) -> None:
        """设置情绪模式

        Args:
            mode: 模拟模式
            value: 固定的情绪分数（仅在 FIXED 模式下使用）
            types: 固定的情绪类型列表（仅在 FIXED 模式下使用）
        """
        if mode == MockMode.FIXED and value is not None and types is not None:
            emotions_value: EmotionsValue = {"types": types, "scores": value}
            self.emotions_config = MockConfig(mode=mode, value=emotions_value)
        else:
            self.emotions_config = MockConfig(mode=mode)

    def set_delay_config(
        self,
        mode: MockMode,
        base_delay: Optional[float] = None,
        random_range: Optional[Tuple[float, float]] = None,
    ) -> None:
        """设置延迟配置

        Args:
            mode: 模拟模式
            base_delay: 基础延迟时间（秒）
            random_range: 随机延迟范围的乘数
        """
        if base_delay is not None:
            self.delay_config.base_delay = base_delay
        if random_range is not None:
            self.delay_config.random_range = random_range
        self.delay_config.mode = mode

    def _get_attack_check(self) -> bool:
        """获取攻击检测结果"""
        if (
            self.attack_config.mode == MockMode.FIXED
            and self.attack_config.value is not None
            and isinstance(self.attack_config.value, bool)
        ):
            return self.attack_config.value
        return random.random() < 0.1  # 10% 概率为 True

    def _get_friend_score(self) -> int:
        """获取友情分数"""
        if (
            self.friend_score_config.mode == MockMode.FIXED
            and self.friend_score_config.value is not None
            and isinstance(self.friend_score_config.value, int)
        ):
            return self.friend_score_config.value
        return random.randint(-5, 5)

    def _get_romance_score(self) -> int:
        """获取浪漫分数"""
        if (
            self.romance_score_config.mode == MockMode.FIXED
            and self.romance_score_config.value is not None
            and isinstance(self.romance_score_config.value, int)
        ):
            return self.romance_score_config.value
        return random.randint(-5, 5)

    def _get_emotions(self) -> Dict[str, int]:
        """获取情绪数据"""
        if (
            self.emotions_config.mode == MockMode.FIXED
            and self.emotions_config.value is not None
            and isinstance(self.emotions_config.value, dict)
        ):
            # 如果是旧格式的 EmotionsValue 类型，转换为新格式
            if "types" in self.emotions_config.value and "scores" in self.emotions_config.value:
                types = self.emotions_config.value["types"]
                scores = self.emotions_config.value["scores"]
                if types and scores:
                    # 只取第一个情绪类型
                    emotion_type = types[0]
                    return {emotion_type: scores.get(emotion_type, 5)}
            else:
                # 已经是新格式
                return self.emotions_config.value

        # 随机模式
        emotion_types = ["anger", "happy", "none"]
        selected_type = random.choice(emotion_types)
        if selected_type == "none":
            return {}
        return {selected_type: random.randint(1, 12)}

    def _generate_mock_content(self, prompt: str) -> str:
        """生成模拟回复内容，返回 JSON 格式的字符串"""
        logger.debug(f"Generating mock content for prompt: {prompt}")

        # 基础回复内容生成
        responses = [
            "我理解你的想法，让我们继续探讨这个话题。",
            "这是一个很有趣的观点，我很认同。",
            "你说得很有道理，我们可以深入交流。",
            "确实如此，这让我想到了一些新的思路。",
        ]

        # 构建新的响应格式
        response_json = {
            "is_attack": self._get_attack_check(),
            "response": True,
            "content": random.choice(responses),
            "emotions": self._get_emotions(),
            "friend_score": self._get_friend_score(),
            "romance_score": self._get_romance_score(),
        }

        # 随机添加总结字段（20% 概率）
        if random.random() < 0.2:
            response_json["summary"] = "这是一个对话总结示例。"

        # 使用 json.dumps 格式化 JSON 字符串
        response = json.dumps(response_json, ensure_ascii=False)
        logger.debug(f"Generated mock content: {response}")
        return response

    async def generate_response(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """模拟大模型 API 响应

        Args:
            request: 包含 messages 等参数的请求字典

        Returns:
            Dict: 模拟的 API 响应
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

            # 获取延迟时间
            delay = self.delay_config.get_delay()
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

    async def validate_response(self, response: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """验证响应是否符合标准 LLM 响应结构

        注意：此方法仅验证 LLM API 响应的结构，不验证响应内容的业务逻辑。
        内容的业务逻辑验证由 context_strategy 负责。

        Args:
            response: LLM 响应内容

        Returns:
            tuple[bool, Optional[str]]: (是否有效, 错误信息)
        """
        if "error" in response:
            error_msg = f"API error: {response['error']}"
            return False, error_msg

        try:
            required_fields = ["id", "object", "created", "model", "choices", "usage"]
            missing_fields = [field for field in required_fields if field not in response]
            if missing_fields:
                return False, f"Missing required fields: {missing_fields}"

            if not response["choices"] or not isinstance(response["choices"], list):
                return False, "Invalid or empty choices field"

            choice = response["choices"][0]
            if not all(key in choice["message"] for key in ["role", "content"]):
                return False, "Invalid message format in choice"

            # 检查 JSON 格式是否有效
            try:
                json.loads(choice["message"]["content"])
            except json.JSONDecodeError:
                return False, "Invalid JSON in response content"

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"
