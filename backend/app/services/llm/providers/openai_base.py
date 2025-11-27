"""
Shared OpenAI SDK adapter utilities.

All providers that rely on the OpenAI-compatible SDK should inherit from
``OpenAIBaseAdapter`` to reuse client construction, error logging and the
template method that orchestrates request handling.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from exceptions.llm import LLMConfigurationError
from models.llm import LLMConfig, LLMProvider
from openai import AsyncOpenAI
from services.llm.types import LLMProviderResult, LLMRequestOptions
from utils.logging import get_logger

logger = get_logger(__name__)


class OpenAIBaseAdapter(ABC):
    """Base adapter that encapsulates OpenAI SDK boilerplate."""

    def create_client(
        self,
        provider: LLMProvider,
        *,
        timeout: Optional[int] = None,
    ) -> AsyncOpenAI:
        """
        Build an AsyncOpenAI client with project defaults.
        """
        api_key = self._get_api_key(provider)
        if not api_key:
            raise LLMConfigurationError(f"API key not configured for provider {provider.display_name}")

        return AsyncOpenAI(
            api_key=api_key,
            base_url=provider.base_url,
            timeout=timeout or 60,
            max_retries=3,
        )

    async def send_request(
        self,
        config: LLMConfig,
        provider: LLMProvider,
        options: LLMRequestOptions,
        *,
        stream: bool = False,
        preemption_checker=None,
    ) -> LLMProviderResult:
        """
        Template method that dispatches an LLM request.
        """
        client = self.create_client(
            provider,
            timeout=options.provider_overrides.get("timeout"),
        )

        params = await self.build_request_params(options)

        if stream:
            return await self._send_streaming_request(
                client=client,
                params=params,
                options=options,
                preemption_checker=preemption_checker,
            )

        response = await self._send_non_streaming_request(
            client=client,
            params=params,
            options=options,
        )
        return await self.parse_response(response, params, options)

    @abstractmethod
    async def build_request_params(
        self,
        options: LLMRequestOptions,
    ) -> Dict[str, Any]:
        """Construct provider specific parameters."""

    @abstractmethod
    async def parse_response(
        self,
        response: Any,
        params: Dict[str, Any],
        options: LLMRequestOptions,
    ) -> LLMProviderResult:
        """Normalize provider response payload."""

    @abstractmethod
    async def _send_non_streaming_request(
        self,
        *,
        client: AsyncOpenAI,
        params: Dict[str, Any],
        options: LLMRequestOptions,
    ) -> Any:
        """
        Execute the non-streaming request using the concrete API method.
        """

    @abstractmethod
    async def _send_streaming_request(
        self,
        *,
        client: AsyncOpenAI,
        params: Dict[str, Any],
        options: LLMRequestOptions,
        preemption_checker,
    ) -> LLMProviderResult:
        """Execute a streaming request and return the normalized result."""

    def _get_api_key(self, provider: LLMProvider) -> Optional[str]:
        """
        Resolve API key from explicitly configured env var or fallback pattern.
        """
        if provider.api_key_env:
            value = os.getenv(provider.api_key_env)
            if value:
                return value

        default_env_name = f"{provider.name.upper()}_API_KEY"
        return os.getenv(default_env_name)
