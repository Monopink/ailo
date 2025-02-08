from typing import Dict
from .base import BaseLLM
from .mock_llm import MockLLM
from .mirrored_llm import MirroredLLM
from .doubao import Doubao

# 创建全局实例
mock_llm = MockLLM()
mirrored_llm = MirroredLLM()

# 创建全局实例字典，方便管理和切换不同的 LLM 实现
llm_instances: Dict[str, BaseLLM] = {
    "mock": MockLLM(),
    "mirrored": MirroredLLM(),
    "doubao": Doubao(
        api_key="6b52b9c6-7ba6-49cd-89f8-3c607f3cc4ae",
        model_id="ep-20250205085837-wkjf7",
    ),
}

# 导出默认实例
default_llm = llm_instances["mock"]
model_lily_llm = llm_instances["doubao"]

__all__ = [
    "BaseLLM",
    "default_llm",
    "model_lily_llm",
]
