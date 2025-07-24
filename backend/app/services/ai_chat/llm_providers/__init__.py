from typing import Dict
import os
from .base import BaseLLM
from .mock_llm import MockLLM
from .mock_json_llm import MockJsonLLM
from .mirrored_llm import MirroredLLM
from .mock_manual_llm import MockLLMManual
from .doubao import Doubao

# Get environment variables with default values
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_MODEL_ID_STANDARD = os.getenv("DOUBAO_MODEL_ID_STANDARD", "")
DOUBAO_MODEL_ID_ADVANCED = os.getenv("DOUBAO_MODEL_ID_ADVANCED", "")

# Create a global instance dictionary for easy management
# and switching between different LLM implementations
llm_instances: Dict[str, BaseLLM] = {
    "mock": MockLLM(),
    "mock_json": MockJsonLLM(),
    "mirrored": MirroredLLM(),
    "mock_manual": MockLLMManual(),
}

# Only add Doubao instances if API key is provided
if DOUBAO_API_KEY and DOUBAO_MODEL_ID_STANDARD:
    llm_instances["doubao_standard"] = Doubao(
        api_key=DOUBAO_API_KEY,
        model_id=DOUBAO_MODEL_ID_STANDARD,
    )

if DOUBAO_API_KEY and DOUBAO_MODEL_ID_ADVANCED:
    llm_instances["doubao_advanced"] = Doubao(
        api_key=DOUBAO_API_KEY,
        model_id=DOUBAO_MODEL_ID_ADVANCED,
    )

# Export default instance - fallback to mock if Doubao is not configured
default_llm = llm_instances.get("doubao_standard", llm_instances["mock"])
model_ailo_standard_llm = llm_instances["mirrored"]
model_ailo_advanced_llm = llm_instances["mirrored"]
# model_ailo_advanced_llm = llm_instances["doubao_advanced"]

__all__ = [
    "BaseLLM",
    "default_llm",
    "model_ailo_standard_llm",
    "model_ailo_advanced_llm",
]
