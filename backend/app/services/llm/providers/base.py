"""
Provider capability declarations for LLM adapters.

The project uses this lightweight dataclass to describe what a provider
supports so that routing, UI and feature toggles can reason about the
adapter without introducing tight coupling between layers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """
    Describes the feature set an adapter supports.

    Attributes
    ----------
    supports_streaming:
        Whether the provider can stream tokens/events.
    supports_json_schema:
        Whether JSON schema constrained output is supported natively.
    supports_caching:
        Whether the provider exposes request/response level caching controls.
    supports_tools:
        Whether the provider can execute tool/function calls.
    message_format:
        Logical format of messages the adapter expects. For example
        ``"responses"`` for Doubao Responses API compatible blocks or
        ``"openai"`` for Chat Completions style messages.
    supports_thinking_mode:
        True if the adapter can toggle advanced reasoning/thinking modes.
    supports_multimodal:
        Whether non-text modalities (images/audio/video) are supported.
    """

    supports_streaming: bool = True
    supports_json_schema: bool = False
    supports_caching: bool = False
    supports_tools: bool = True
    message_format: str = "responses"
    supports_thinking_mode: bool = False
    supports_multimodal: bool = False
