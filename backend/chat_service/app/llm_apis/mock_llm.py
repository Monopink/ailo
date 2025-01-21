import asyncio
import random
from .base import BaseLLMAPI

class MockLLMAPI(BaseLLMAPI):
    async def generate_response(self, prompt: str) -> str:
        """
        模拟大模型API响应
        Args:
            prompt: 输入的提示词
        Returns:
            str: 模拟的API响应
        """
        try:
            # 模拟 API 调用延迟
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # 生成模拟回复内容
            response = self._generate_mock_content(prompt)
            return self.format_response(response)

        except Exception as e:
            return f"抱歉，生成回复时出现错误：{str(e)}"

    def _generate_mock_content(self, prompt: str) -> str:
        """
        生成模拟回复内容
        """
        # 简单的回复生成逻辑
        keywords = ["有趣", "理解", "建议", "想法", "感觉", "希望", "开心", "思考"]
        responses = [
            f"我{random.choice(keywords)}你说的内容。",
            f"这确实是个值得{random.choice(keywords)}的话题。",
            f"听你这么说，我也有了新的{random.choice(keywords)}。",
            f"我们可以一起{random.choice(keywords)}这个问题。"
        ]
        
        return random.choice(responses)

    async def validate_response(self, response: str) -> bool:
        """
        验证响应是否合适
        """
        return bool(response and len(response) >= 10)