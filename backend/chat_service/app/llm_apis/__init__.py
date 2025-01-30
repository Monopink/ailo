from typing import Dict
from .base import BaseLLM
from .mock_llm import MockLLM
from .mirrored_llm import MirroredLLM

# 创建全局实例
mock_llm = MockLLM()
mirrored_llm = MirroredLLM()

# 创建全局实例字典，方便管理和切换不同的 LLM 实现
llm_instances: Dict[str, BaseLLM] = {
    'mock': MockLLM(),
    'mirrored': MirroredLLM(),
}

# 导出默认实例
default_llm = llm_instances['mock']

__all__ = [
    'BaseLLM',
    'default_llm',
    'llm_instances',
    'mock_llm',
    'mirrored_llm'
]