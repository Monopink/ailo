from typing import Dict
from .base import BaseLLM
from .mock_llm import MockLLM
from .mock_json_llm import MockJsonLLM
from .mirrored_llm import MirroredLLM
from .mock_manual_llm import MockLLMManual
from .doubao import Doubao

# Create a global instance dictionary for easy management
# and switching between different LLM implementations
llm_instances: Dict[str, BaseLLM] = {
    "mock": MockLLM(),
    "mock_json": MockJsonLLM(),
    "mirrored": MirroredLLM(),
    "mock_manual": MockLLMManual(),
    "doubao_pro_32k": Doubao(
        api_key="6b52b9c6-7ba6-49cd-89f8-3c607f3cc4ae",
        model_id="ep-20250205085837-wkjf7",
    ),
}

# Export default instance
default_llm = llm_instances["mock"]
# model_lily_llm = llm_instances["doubao_pro_32k"]
model_lily_llm = llm_instances["mock_manual"]

__all__ = [
    "BaseLLM",
    "default_llm",
    "model_lily_llm",
]
