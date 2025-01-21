from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseLLMAPI(ABC):
    def __init__(self):
        self.api_key = None
        self.api_base = None
        self.default_params = {
            'temperature': 0.7,
            'max_tokens': 1000,
            'top_p': 0.9,
        }

    @abstractmethod
    async def generate_response(self, prompt: dict) -> dict:
        """
        生成大模型响应
        Args:
            prompt: 输入的提示词
        Returns:
            str: 大模型的响应
        """
        pass

    @abstractmethod
    async def validate_response(self, response: str) -> bool:
        """
        验证响应是否有效
        Args:
            response: 大模型的响应
        Returns:
            bool: 响应是否有效
        """
        pass

    def build_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """
        构建提示词
        """
        style = context.get('style', '')
        relationship = context.get('relationship_type', 'stranger')
        long_term_memory = context.get('long_term_memory', '')
        
        prompt = f"""
        作为一个 AI 助手，请按照以下设定回复：
        - 性格风格：{style}
        - 关系类型：{relationship}
        - 背景知识：{long_term_memory}
        
        用户说：{user_input}
        
        请用自然、流畅的语言回复，保持设定的性格风格。
        """
        return prompt

    def format_response(self, response: str) -> str:
        """
        格式化响应内容
        Args:
            response: 原始响应内容
        Returns:
            str: 格式化后的响应内容
        """
        if not response:
            return ""
        return response.strip()