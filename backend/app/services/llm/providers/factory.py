"""
Provider adapter factory.

Resolves the correct adapter for a provider/config and dispatches requests.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Dict, Optional

from models.llm import LLMConfig, LLMProvider
from services.llm.types import LLMRequestOptions, LLMProviderResult
from utils.logging import get_logger

logger = get_logger(__name__)

PROVIDER_ADAPTERS: Dict[str, str] = {
    "doubao": "openai_sdk",
    "qwen": "openai_sdk",
    "deepseek": "openai_sdk",
    "mock": "mock",
}


async def send_request(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    *,
    stream: bool = False,
    preemption_checker: Optional[Callable[[], Awaitable[bool]]] = None,
) -> LLMProviderResult:
    """
    Route the LLM request to the correct adapter.
    """
    adapter_name = PROVIDER_ADAPTERS.get(provider.name, "openai_sdk")

    logger.debug(
        "llm_adapter_selected",
        provider=provider.name,
        adapter=adapter_name,
    )

    if adapter_name == "mock":
        from . import mock as adapter
    elif adapter_name == "openai_sdk":
        from . import openai_sdk as adapter
    else:
        raise ValueError(f"Unsupported adapter: {adapter_name}")

    return await adapter.send_request(
        config=config,
        provider=provider,
        options=options,
        stream=stream,
        preemption_checker=preemption_checker,
    )
