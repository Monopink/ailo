"""
Streaming decision helpers for LLM requests.

Encapsulates all logic that determines whether a given invocation should
use streaming or fallback to standard responses.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from models.llm import LLMConfig, LLMProvider
from services.llm.types import LLMStreamingDecision


def extract_stream_override(overrides: Optional[Dict[str, Any]]) -> Optional[bool]:
    """Return per-request streaming override if provided."""
    if not isinstance(overrides, dict):
        return None

    if "enable_streaming" in overrides:
        return _coerce_bool(overrides.get("enable_streaming"))

    if "stream" in overrides:
        return _coerce_bool(overrides.get("stream"))

    return None


def resolve_streaming_decision(
    *,
    config: LLMConfig,
    provider: LLMProvider,
    enable_override: Optional[bool],
    has_preemption_checker: bool,
) -> LLMStreamingDecision:
    requested = enable_override if enable_override is not None else bool(getattr(config, "enable_streaming", False))
    override_applied = enable_override is not None

    if not requested:
        return LLMStreamingDecision(
            should_stream=False,
            requested=False,
            reason="disabled_by_config" if not override_applied else "disabled_by_override",
            override_applied=override_applied,
        )

    if provider.supports_streaming != 1:
        return LLMStreamingDecision(
            should_stream=False,
            requested=True,
            reason="provider_not_supported",
            override_applied=override_applied,
        )

    if not has_preemption_checker:
        return LLMStreamingDecision(
            should_stream=False,
            requested=True,
            reason="missing_preemption_checker",
            override_applied=override_applied,
        )

    return LLMStreamingDecision(
        should_stream=True,
        requested=True,
        reason="ok",
        override_applied=override_applied,
    )


def _coerce_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return None
