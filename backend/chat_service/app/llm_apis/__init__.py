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
    "doubao-1.5-pro-32k": Doubao(
        api_key="6b52b9c6-7ba6-49cd-89f8-3c607f3cc4ae",
        model_id="ep-20250619205259-nzbw8",
    ),
    "doubao-seed-1.6": Doubao(
        api_key="6b52b9c6-7ba6-49cd-89f8-3c607f3cc4ae",
        model_id="ep-20250619205554-wwsr7",
    ),
}

# Export default instance
default_llm = llm_instances["doubao-1.5-pro-32k"]
model_ailo_standard_llm = llm_instances["mock_manual"]
model_ailo_advanced_llm = llm_instances["mock_manual"]
# model_ailo_advanced_llm = llm_instances["doubao-seed-1.6"]

__all__ = [
    "BaseLLM",
    "default_llm",
    "model_ailo_standard_llm",
    "model_ailo_advanced_llm",
]
