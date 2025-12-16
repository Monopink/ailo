"""
Provider adapter factory.

Resolves the correct adapter for a provider/config and dispatches requests.
"""

from __future__ import annotations

from app.models.llm import LLMConfig, LLMProvider
from app.type_defs import LLMProviderResult, LLMRequestOptions, PreemptionChecker
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Import all adapters at module level
from . import doubao_responses, mock

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
    preemption_checker: PreemptionChecker | None = None,
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
        return await _call_mock_adapter(
            config=config,
            provider=provider,
            options=options,
            stream=stream,
            preemption_checker=preemption_checker,
        )
    if adapter_name == "doubao_responses":
        return await _call_doubao_adapter(
            config=config,
            provider=provider,
            options=options,
            stream=stream,
            preemption_checker=preemption_checker,
        )
    raise ValueError(f"Adapter '{adapter_name}' not registered. Available: mock, doubao_responses")


async def _call_mock_adapter(
    *,
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    stream: bool,
    preemption_checker: PreemptionChecker | None,
) -> LLMProviderResult:
    response: LLMProviderResult = await mock.send_request(
        config=config,
        provider=provider,
        options=options,
        stream=stream,
        preemption_checker=preemption_checker,
    )
    return response


async def _call_doubao_adapter(
    *,
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    stream: bool,
    preemption_checker: PreemptionChecker | None,
) -> LLMProviderResult:
    response: LLMProviderResult = await doubao_responses.send_request(
        config=config,
        provider=provider,
        options=options,
        stream=stream,
        preemption_checker=preemption_checker,
    )
    return response
