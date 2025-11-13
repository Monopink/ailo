"""
Doubao Responses API adapter built on top of the OpenAI SDK.

The adapter normalizes message payloads, wires common request kwargs and
delegates client creation/error handling to :class:`OpenAIBaseAdapter`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from exceptions.llm import LLMConfigurationError, LLMRequestError, LLMTimeoutError
from models.llm import LLMConfig, LLMProvider
from services.llm.converters import ResponsesFormatConverter
from services.llm.providers.base import ProviderCapabilities
from services.llm.providers.openai_base import OpenAIBaseAdapter
from services.llm.types import LLMProviderResult, LLMRequestOptions
from utils.logging import get_logger

logger = get_logger(__name__)

CAPABILITIES = ProviderCapabilities(
    supports_streaming=True,
    supports_json_schema=True,
    supports_caching=True,
    supports_tools=True,
    message_format="responses",
    supports_multimodal=True,
)

_converter = ResponsesFormatConverter()

_ALLOWED_PARAM_OVERRIDES: Tuple[str, ...] = (
    "metadata",
    "response_format",
    "reasoning",
    "modalities",
    "audio",
    "instructions",
)


class DoubaoResponsesAdapter(OpenAIBaseAdapter):
    """Adapter for Doubao/OpenAI Responses API."""

    async def build_request_params(
        self,
        options: LLMRequestOptions,
    ) -> Dict[str, Any]:
        call_params = _build_responses_call_params(options)
        request_kwargs = _build_request_kwargs(options)
        return {"call_params": call_params, "request_kwargs": request_kwargs}

    async def parse_response(
        self,
        response: Any,
        params: Dict[str, Any],
        options: LLMRequestOptions,
    ) -> LLMProviderResult:
        content, tool_calls, reasoning_content = _extract_responses_text(response)
        usage = _usage_to_dict(getattr(response, "usage", None))

        return LLMProviderResult(
            content=content,
            model=getattr(response, "model", None),
            usage=usage,
            finish_reason=_extract_finish_reason(response),
            raw_response=response.to_dict() if hasattr(response, "to_dict") else None,
            request_params=params.get("call_params"),
            response_id=getattr(response, "id", None),
            cache_hit=_is_cache_hit(usage),
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
        )

    async def _send_non_streaming_request(
        self,
        *,
        client: AsyncOpenAI,
        params: Dict[str, Any],
        options: LLMRequestOptions,
    ) -> Any:
        try:
            return await client.responses.create(
                **params["call_params"],
                **params["request_kwargs"],
            )
        except (LLMTimeoutError, LLMRequestError):
            raise
        except Exception as exc:  # pragma: no cover - safety net
            logger.error("responses_request_failed", error=str(exc), exc_info=True)
            raise LLMRequestError(provider="doubao", message=str(exc)) from exc

    async def _send_streaming_request(
        self,
        *,
        client: AsyncOpenAI,
        params: Dict[str, Any],
        options: LLMRequestOptions,
        preemption_checker,
    ) -> LLMProviderResult:
        call_params = params["call_params"]
        request_kwargs = dict(params["request_kwargs"])

        accumulated_text_parts: List[str] = []
        accumulated_tool_calls: List[Dict[str, Any]] = []
        accumulated_reasoning_parts: List[str] = []
        final_model = call_params["model"]
        final_usage: Optional[Dict[str, Any]] = None
        final_response_id: Optional[str] = None
        final_finish_reason: Optional[str] = None

        try:
            stream = await client.responses.create(
                **call_params,
                **request_kwargs,
                stream=True,
            )

            logger.debug("stream_started", model=call_params["model"])
            chunk_count = 0

            async for chunk in stream:
                chunk_count += 1

                if preemption_checker and await preemption_checker():
                    logger.info("stream_preempted", chunks_processed=chunk_count)
                    return LLMProviderResult(
                        content=None,
                        model=final_model,
                        usage=None,
                        finish_reason="preempted",
                        raw_response=None,
                        request_params=call_params,
                        preempted=True,
                    )

                if getattr(chunk, "id", None):
                    final_response_id = chunk.id
                if getattr(chunk, "model", None):
                    final_model = chunk.model
                if getattr(chunk, "usage", None):
                    final_usage = _usage_to_dict(chunk.usage)
                if getattr(chunk, "status", None):
                    final_finish_reason = chunk.status

                _process_stream_chunk(
                    chunk=chunk,
                    accumulated_text_parts=accumulated_text_parts,
                    accumulated_tool_calls=accumulated_tool_calls,
                    accumulated_reasoning_parts=accumulated_reasoning_parts,
                )

            content = "".join(accumulated_text_parts)
            reasoning_content = "\n".join(filter(None, accumulated_reasoning_parts)) or None

            return LLMProviderResult(
                content=content,
                model=final_model,
                usage=final_usage,
                finish_reason=final_finish_reason or "completed",
                raw_response=None,
                request_params=call_params,
                response_id=final_response_id,
                cache_hit=_is_cache_hit(final_usage),
                tool_calls=accumulated_tool_calls or None,
                reasoning_content=reasoning_content,
            )

        except (LLMTimeoutError, LLMRequestError):
            raise
        except Exception as exc:
            logger.error("stream_responses_failed", error=str(exc), exc_info=True)
            raise LLMRequestError(
                provider="doubao", message=f"Streaming failed: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Module level entry point
# ---------------------------------------------------------------------------


async def send_request(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    *,
    stream: bool = False,
    preemption_checker=None,
) -> LLMProviderResult:
    """Factory-facing entry point."""
    adapter = DoubaoResponsesAdapter()
    return await adapter.send_request(
        config=config,
        provider=provider,
        options=options,
        stream=stream,
        preemption_checker=preemption_checker,
    )


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def _build_responses_call_params(options: LLMRequestOptions) -> Dict[str, Any]:
    """
    Build the set of direct parameters accepted by Responses API.
    """
    params: Dict[str, Any] = {
        "model": options.model,
        "input": _converter.convert_to_provider_format(options.messages),
    }

    if options.caching.previous_response_id:
        params["previous_response_id"] = options.caching.previous_response_id

    model_override = options.provider_overrides.get("model_override") or options.provider_overrides.get(
        "model"
    )
    if isinstance(model_override, str):
        params["model"] = model_override

    manual_params = options.provider_overrides.get("params_override")
    if isinstance(manual_params, dict):
        allowed = {k: v for k, v in manual_params.items() if k in _ALLOWED_PARAM_OVERRIDES}
        ignored = sorted(k for k in manual_params if k not in _ALLOWED_PARAM_OVERRIDES)
        if ignored:
            logger.warning(
                "responses_params_override_ignored",
                ignored_keys=ignored,
                message="Unsupported Responses API parameters were dropped",
            )
        if allowed:
            params.update(allowed)

    return params


def _build_request_kwargs(options: LLMRequestOptions) -> Dict[str, Any]:
    """
    Build kwargs (extra headers/body/query) for Responses API invocation.
    """
    extra_body = dict(options.extra_body or {})

    if options.temperature is not None:
        extra_body["temperature"] = options.temperature
    if options.top_p is not None:
        extra_body["top_p"] = options.top_p
    if options.max_tokens is not None:
        extra_body["max_output_tokens"] = options.max_tokens
    if options.stop_sequences:
        extra_body["stop"] = options.stop_sequences

    if options.tools:
        extra_body["tools"] = options.tools
        if options.tool_choice:
            extra_body["tool_choice"] = options.tool_choice
        if options.max_tool_calls:
            extra_body["max_tool_calls"] = options.max_tool_calls

    if options.json_schema:
        text_format_payload = _build_json_schema_format(options.json_schema)
        extra_body["text"] = _merge_text_format(extra_body.get("text"), text_format_payload)

    if options.caching.enabled and options.caching.strategy != "none":
        caching_payload: Dict[str, Any] = {"type": "enabled"}
        if options.caching.strategy == "prefix":
            caching_payload["prefix"] = True
        if options.caching.ttl_seconds:
            caching_payload["ttl"] = options.caching.ttl_seconds
        extra_body["caching"] = caching_payload

    overrides_extra_body = options.provider_overrides.get("extra_body")
    if isinstance(overrides_extra_body, dict):
        extra_body.update(overrides_extra_body)

    override_headers = options.provider_overrides.get("extra_headers")
    merged_headers: Dict[str, Any] = dict(options.extra_headers or {})
    if isinstance(override_headers, dict):
        merged_headers.update(override_headers)

    override_query = options.provider_overrides.get("extra_query")
    merged_query: Dict[str, Any] = dict(options.extra_query or {})
    if isinstance(override_query, dict):
        merged_query.update(override_query)

    _validate_extra_body(extra_body)

    return {
        "extra_headers": merged_headers or None,
        "extra_query": merged_query or None,
        "extra_body": extra_body or None,
        "timeout": options.provider_overrides.get("timeout"),
    }


def _validate_extra_body(extra_body: Dict[str, Any]) -> None:
    """Ensure no legacy Chat Completions fields are present."""
    unsupported_keys = sorted(key for key in ("response_format", "thinking") if key in extra_body)
    if unsupported_keys:
        raise LLMConfigurationError(
            f"Unsupported Responses payload fields detected: {', '.join(unsupported_keys)}. "
            "Please migrate to text.format and disable legacy thinking settings."
        )


def _build_json_schema_format(schema_definition: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "ai_response",
        "schema": schema_definition,
        "strict": True,
    }


def _merge_text_format(existing_text: Any, format_payload: Dict[str, Any]) -> Dict[str, Any]:
    text_section: Dict[str, Any] = {}
    if isinstance(existing_text, dict):
        text_section.update(existing_text)
    text_section["format"] = format_payload
    return text_section


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _process_stream_chunk(
    *,
    chunk: Any,
    accumulated_text_parts: List[str],
    accumulated_tool_calls: List[Dict[str, Any]],
    accumulated_reasoning_parts: List[str],
) -> None:
    output_list = getattr(chunk, "output", None)
    if not output_list:
        return

    for output in output_list:
        output_type = getattr(output, "type", None)

        summary_blocks = getattr(output, "summary", None)
        if summary_blocks:
            accumulated_reasoning_parts.extend(_collect_text_blocks(summary_blocks))

        if output_type == "message":
            content_blocks = getattr(output, "content", None)
            if content_blocks:
                for part in content_blocks:
                    if getattr(part, "type", None) == "output_text":
                        text = getattr(part, "text", None)
                        if text:
                            accumulated_text_parts.append(text)
        elif output_type in {"function_call", "function"}:
            try:
                accumulated_tool_calls.append(output.to_dict())
            except AttributeError:
                accumulated_tool_calls.append({"type": output_type})


def _extract_responses_text(response: Any) -> Tuple[str, Optional[List[Dict[str, Any]]], Optional[str]]:
    text_parts: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    reasoning_parts: List[str] = []

    for output in getattr(response, "output", []) or []:
        output_type = getattr(output, "type", None)

        summary_blocks = getattr(output, "summary", None)
        if summary_blocks:
            reasoning_parts.extend(_collect_text_blocks(summary_blocks))

        if output_type == "message":
            for part in getattr(output, "content", []) or []:
                if getattr(part, "type", None) == "output_text":
                    text_parts.append(part.text or "")
        elif output_type in {"function_call", "function"}:
            try:
                tool_calls.append(output.to_dict())
            except AttributeError:
                tool_calls.append({"type": output_type})

    content = "\n".join(filter(None, text_parts))
    reasoning_content = "\n".join(filter(None, reasoning_parts)) or None
    return content, tool_calls or None, reasoning_content


def _collect_text_blocks(blocks: Any) -> List[str]:
    collected: List[str] = []
    if not blocks:
        return collected

    for block in blocks:
        text_value = getattr(block, "text", None)
        if text_value is None and isinstance(block, dict):
            text_value = block.get("text")
        if text_value:
            collected.append(text_value)
    return collected


def _extract_finish_reason(response: Any) -> Optional[str]:
    try:
        choices = getattr(response, "output", None)
        if choices:
            for choice in choices:
                if getattr(choice, "type", None) == "message":
                    metadata = getattr(choice, "metadata", None)
                    if metadata and "finish_reason" in metadata:
                        return metadata["finish_reason"]
        return getattr(response, "status", None)
    except Exception:  # pragma: no cover - defensive
        return None


def _usage_to_dict(usage: Any) -> Optional[Dict[str, Any]]:
    if usage is None:
        return None
    try:
        return usage.to_dict()
    except AttributeError:
        return usage if isinstance(usage, dict) else None


def _is_cache_hit(usage: Optional[Dict[str, Any]]) -> bool:
    if not usage:
        return False
    input_details = usage.get("input_tokens_details") or {}
    cached_tokens = input_details.get("cached_tokens") or 0
    return cached_tokens > 0


__all__ = [
    "CAPABILITIES",
    "DoubaoResponsesAdapter",
    "send_request",
    "_validate_extra_body",
]
