"""
LLM request/response data structures.

These dataclasses provide a shared contract between the LLM client and
provider adapters. They keep configuration/override handling explicit
and make it easier to extend request capabilities (tools, caching, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
    previous_response_id: Optional[str] = None
    ttl_seconds: Optional[int] = None


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
    messages: List[Dict[str, Any]]
    json_schema: Optional[Dict[str, Any]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop_sequences: Optional[List[str]] = None
    thinking_mode: Optional[str] = None
    tools: List[Dict[str, Any]] = field(default_factory=list)
    tool_choice: Optional[str] = None
    parallel_tool_calls: Optional[bool] = None
    max_tool_calls: Optional[int] = None
    extra_headers: Dict[str, Any] = field(default_factory=dict)
    extra_query: Dict[str, Any] = field(default_factory=dict)
    extra_body: Dict[str, Any] = field(default_factory=dict)
    caching: LLMCachingOptions = field(default_factory=LLMCachingOptions)
    provider_overrides: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMProviderResult:
    """Normalized provider response."""

    content: Optional[Any]
    model: Optional[str]
    usage: Optional[Dict[str, Any]]
    finish_reason: Optional[str]
    raw_response: Optional[Dict[str, Any]] = None
    request_params: Optional[Dict[str, Any]] = None
    response_id: Optional[str] = None
    cache_hit: bool = False
    tool_calls: Optional[List[Dict[str, Any]]] = None
    reasoning_content: Optional[str] = None
    preempted: bool = False
