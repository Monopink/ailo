"""
LLM request/response data structures.

These dataclasses provide a shared contract between the LLM client and
provider adapters. They keep configuration/override handling explicit
and make it easier to extend request capabilities (tools, caching, etc.).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.type_defs.common import JSONDict, JSONValue

type ProviderMessage = dict[str, JSONValue]
type ProviderTool = dict[str, JSONValue]
type PreemptionChecker = Callable[[], Awaitable[bool]]


@dataclass
class LLMSessionContext:
    """Conversation session identifiers used for caching."""

    user_qiao_id: str
    instance_qiao_id: str


@dataclass
class LLMCachingOptions:
    """Provider caching configuration."""

    enabled: bool = False
    strategy: str = "none"
    previous_response_id: str | None = None
    ttl_seconds: int | None = None


@dataclass
class LLMStreamingDecision:
    """Result of streaming eligibility evaluation."""

    should_stream: bool
    requested: bool
    reason: str
    override_applied: bool = False


@dataclass
class LLMRequestOptions:
    """Normalized request parameters passed to provider adapters."""

    model: str
    messages: list[ProviderMessage]
    json_schema: JSONDict | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop_sequences: list[str] | None = None
    thinking_mode: str | None = None
    tools: list[ProviderTool] = field(default_factory=list)
    tool_choice: str | None = None
    parallel_tool_calls: bool | None = None
    max_tool_calls: int | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra_query: dict[str, str] = field(default_factory=dict)
    extra_body: JSONDict = field(default_factory=dict)
    caching: LLMCachingOptions = field(default_factory=LLMCachingOptions)
    provider_overrides: JSONDict = field(default_factory=dict)


@dataclass
class LLMProviderResult:
    """Normalized provider response."""

    content: JSONValue | None
    model: str | None
    usage: JSONDict | None
    finish_reason: str | None
    raw_response: JSONDict | None = None
    request_params: JSONDict | None = None
    response_id: str | None = None
    cache_hit: bool = False
    tool_calls: list[ProviderTool] | None = None
    reasoning_content: str | None = None
    preempted: bool = False


__all__ = [
    "LLMCachingOptions",
    "LLMProviderResult",
    "LLMRequestOptions",
    "LLMSessionContext",
    "LLMStreamingDecision",
    "PreemptionChecker",
    "ProviderMessage",
    "ProviderTool",
]
