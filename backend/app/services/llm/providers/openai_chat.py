"""
Placeholder adapter for future OpenAI Chat Completions support.

The Responses adapter is the only active implementation today, but we
expose this module so that the factory can resolve a symbolic entry once
Chat Completions or compatible providers are reintroduced.
"""

from __future__ import annotations

from models.llm import LLMConfig, LLMProvider
from services.llm.providers.base import ProviderCapabilities
from services.llm.types import LLMProviderResult, LLMRequestOptions

CAPABILITIES = ProviderCapabilities(
    supports_streaming=True,
    supports_json_schema=False,
    supports_caching=False,
    supports_tools=True,
    message_format="openai",
    supports_multimodal=True,
)


async def send_request(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    *,
    stream: bool = False,
    preemption_checker=None,
) -> LLMProviderResult:  # pragma: no cover - placeholder
    raise NotImplementedError(
        "OpenAI Chat Completions adapter not implemented. Use doubao_responses."
    )
