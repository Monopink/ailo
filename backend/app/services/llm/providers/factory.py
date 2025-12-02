"""
Provider adapter factory.

Resolves the correct adapter for a provider/config and dispatches requests.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from models.llm import LLMConfig, LLMProvider
from services.llm.types import LLMProviderResult, LLMRequestOptions
from utils.logging import get_logger

logger = get_logger(__name__)

PROVIDER_ADAPTERS: dict[str, str] = {
    "doubao": "doubao_responses",
    "mock": "mock",
}


async def send_request(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    *,
    stream: bool = False,
    preemption_checker: Callable[[], Awaitable[bool]] | None = None,
) -> LLMProviderResult:
    """
    Route the LLM request to the correct adapter.
    """
    adapter_name = PROVIDER_ADAPTERS.get(provider.name)

    logger.debug(
        "llm_adapter_selected",
        provider=provider.name,
        adapter=adapter_name,
    )

    if adapter_name is None:
        raise ValueError(
            f"Provider '{provider.name}' is not mapped to an adapter. "
            "Add a dedicated provider adapter before enabling this provider."
        )

    if adapter_name == "mock":
        from . import mock as adapter
    elif adapter_name == "doubao_responses":
        from . import doubao_responses as adapter
    elif adapter_name == "openai_chat":
        from . import openai_chat as adapter
    else:
        raise ValueError(f"Unsupported adapter: {adapter_name}")

    return await adapter.send_request(
        config=config,
        provider=provider,
        options=options,
        stream=stream,
        preemption_checker=preemption_checker,
    )
