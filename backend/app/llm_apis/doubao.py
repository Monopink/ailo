import asyncio
import random
from typing import Dict, Any
from .base import BaseLLMAPI

class DouBaoAPI(BaseLLMAPI):
    def __init__(self):
        super().__init__()
        self.api_base = "https://api.doubao.com/v1"  # 示例 API 地址
        self.response_templates = {
            'stranger': [
                "您好！{content}",
                "这个问题很有趣，{content}",
                "确实如此，{content}",
            ],
            'friend': [
                "哈哈，{content}",
                "说得对啊，{content}",
                "我觉得吧，{content}",
            ],
            'confidant': [
                "亲爱的朋友，{content}",
                "你说得很对呢，{content}",
                "其实我觉得吧，{content}",
            ],
            'lover': [
                "亲爱的，{content}",
                "宝贝，{content}",
                "我同意你的看法，{content}",
            ]
        }

    async def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """
        模拟生成响应
        """
        try:
            # 模拟 API 调用延迟
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
            # 获取关系类型
            relationship = context.get('relationship_type', 'stranger')
            
            # 根据关系类型选择响应模板
            templates = self.response_templates.get(relationship, self.response_templates['stranger'])
            template = random.choice(templates)
            
            # 生成模拟回复内容
            response_content = self._generate_mock_content(prompt)
            
            # 使用模板格式化响应
            response = template.format(content=response_content)
            
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
        # 简单的验证逻辑
        if not response or len(response) < 10:
            return False
        return True