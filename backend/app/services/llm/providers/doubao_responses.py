"""
Doubao Responses API adapter built on top of the OpenAI SDK.

The adapter normalizes message payloads, wires common request kwargs and
delegates client creation/error handling to :class:`OpenAIBaseAdapter`.
"""

from __future__ import annotations

from typing import Any, cast

from openai import AsyncOpenAI

from app.exceptions.llm import LLMConfigurationError, LLMRequestError, LLMTimeoutError
from app.models.llm import LLMConfig, LLMProvider
from app.services.llm.converters import ResponsesFormatConverter
from app.services.llm.providers.base import ProviderCapabilities
from app.services.llm.providers.openai_base import OpenAIBaseAdapter
from app.type_defs import (
    JSONDict,
    JSONValue,
    LLMProviderResult,
    LLMRequestOptions,
    PreemptionChecker,
)
from app.utils.logging import get_logger

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

_ALLOWED_PARAM_OVERRIDES: tuple[str, ...] = (
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
    ) -> dict[str, JSONDict]:
        call_params = _build_responses_call_params(options)
        request_kwargs = _build_request_kwargs(options)
        return {"call_params": call_params, "request_kwargs": request_kwargs}

    async def parse_response(
        self,
        response: JSONDict,
        params: dict[str, JSONDict],
        options: LLMRequestOptions,  # noqa: ARG002
    ) -> LLMProviderResult:
        content, tool_calls, reasoning_content = _extract_responses_text(response)
        usage = _usage_to_dict(getattr(response, "usage", None))
        call_params = params.get("call_params")

        return LLMProviderResult(
            content=content,
            model=getattr(response, "model", None),
            usage=usage,
            finish_reason=_extract_finish_reason(response),
            raw_response=response.to_dict() if hasattr(response, "to_dict") else None,
            request_params=call_params if isinstance(call_params, dict) else None,
            response_id=getattr(response, "id", None),
            cache_hit=_is_cache_hit(usage),
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
        )

    async def _send_non_streaming_request(
        self,
        *,
        client: AsyncOpenAI,
        params: dict[str, JSONDict],
        options: LLMRequestOptions,  # noqa: ARG002
    ) -> JSONDict:
        call_params = cast(dict[str, Any], params["call_params"])
        request_kwargs = cast(dict[str, Any], params["request_kwargs"])
        create_fn = cast(Any, client.responses.create)
        try:
            response = await create_fn(**call_params, **request_kwargs)
            if hasattr(response, "to_dict"):
                response_dict = response.to_dict()
                if isinstance(response_dict, dict):
                    return response_dict
            return dict(response)
        except (LLMTimeoutError, LLMRequestError):
            raise
        except Exception as exc:  # pragma: no cover - safety net
            logger.error("responses_request_failed", error=str(exc), exc_info=True)
            raise LLMRequestError(provider="doubao", message=str(exc)) from exc

    async def _send_streaming_request(
        self,
        *,
        client: AsyncOpenAI,
        params: dict[str, JSONDict],
        options: LLMRequestOptions,  # noqa: ARG002
        preemption_checker: PreemptionChecker | None,
    ) -> LLMProviderResult:
        call_params = cast(dict[str, Any], params["call_params"])
        request_kwargs = cast(dict[str, Any], params["request_kwargs"])
        create_fn = cast(Any, client.responses.create)

        accumulated_text_parts: list[str] = []
        accumulated_tool_calls: list[JSONDict] = []
        accumulated_reasoning_parts: list[str] = []
        final_model: str | None = _coerce_model(call_params.get("model"))
        final_usage: JSONDict | None = None
        final_response_id: str | None = None
        final_finish_reason: str | None = None

        try:
            stream = await create_fn(
                **call_params,
                **request_kwargs,
                stream=True,
            )

            logger.debug("stream_started", model=final_model)
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

                chunk_model = getattr(chunk, "model", None)
                if isinstance(chunk_model, str):
                    final_model = chunk_model
                if getattr(chunk, "id", None):
                    final_response_id = chunk.id
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
            raise LLMRequestError(provider="doubao", message=f"Streaming failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Module level entry point
# ---------------------------------------------------------------------------


async def send_request(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    *,
    stream: bool = False,
    preemption_checker: PreemptionChecker | None = None,
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


def _build_responses_call_params(options: LLMRequestOptions) -> JSONDict:
    """
    Build the set of direct parameters accepted by Responses API.
    """
    params: JSONDict = {
        "model": options.model,
        "input": cast(JSONValue, _converter.convert_to_provider_format(options.messages)),
    }

    if options.caching.previous_response_id:
        params["previous_response_id"] = options.caching.previous_response_id

    model_override = options.provider_overrides.get(
        "model_override"
    ) or options.provider_overrides.get("model")
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


def _build_request_kwargs(options: LLMRequestOptions) -> JSONDict:
    """
    Build kwargs (extra headers/body/query) for Responses API invocation.
    """
    extra_body: JSONDict = dict(options.extra_body or {})

    if options.temperature is not None:
        extra_body["temperature"] = options.temperature
    if options.top_p is not None:
        extra_body["top_p"] = options.top_p
    if options.max_tokens is not None:
        extra_body["max_output_tokens"] = options.max_tokens
    if options.stop_sequences:
        extra_body["stop"] = cast(JSONValue, options.stop_sequences)

    if options.tools:
        extra_body["tools"] = cast(JSONValue, options.tools)
        if options.tool_choice:
            extra_body["tool_choice"] = options.tool_choice
        if options.max_tool_calls:
            extra_body["max_tool_calls"] = options.max_tool_calls

    if options.json_schema:
        text_format_payload = _build_json_schema_format(options.json_schema)
        existing_text = extra_body.get("text")
        extra_body["text"] = _merge_text_format(
            existing_text if isinstance(existing_text, dict) else None,
            text_format_payload,
        )

    if options.caching.enabled and options.caching.strategy != "none":
        caching_payload: JSONDict = {"type": "enabled"}
        if options.caching.strategy == "prefix":
            caching_payload["prefix"] = True
        if options.caching.ttl_seconds:
            caching_payload["ttl"] = options.caching.ttl_seconds
        extra_body["caching"] = caching_payload

    overrides_extra_body = options.provider_overrides.get("extra_body")
    if isinstance(overrides_extra_body, dict):
        extra_body.update(overrides_extra_body)

    override_headers = options.provider_overrides.get("extra_headers")
    merged_headers: JSONDict = dict(options.extra_headers or {})
    if isinstance(override_headers, dict):
        merged_headers.update(override_headers)

    override_query = options.provider_overrides.get("extra_query")
    merged_query: JSONDict = dict(options.extra_query or {})
    if isinstance(override_query, dict):
        merged_query.update(override_query)

    _validate_extra_body(extra_body)

    return {
        "extra_headers": merged_headers or None,
        "extra_query": merged_query or None,
        "extra_body": extra_body or None,
        "timeout": options.provider_overrides.get("timeout"),
    }


def _validate_extra_body(extra_body: JSONDict) -> None:
    """Ensure no legacy Chat Completions fields are present."""
    unsupported_keys = sorted(key for key in ("response_format", "thinking") if key in extra_body)
    if unsupported_keys:
        raise LLMConfigurationError(
            f"Unsupported Responses payload fields detected: {', '.join(unsupported_keys)}. "
            "Please migrate to text.format and disable legacy thinking settings."
        )


def _build_json_schema_format(schema_definition: JSONDict) -> JSONDict:
    return {
        "type": "json_schema",
        "name": "ai_response",
        "schema": schema_definition,
        "strict": True,
    }


def _merge_text_format(existing_text: JSONDict | None, format_payload: JSONDict) -> JSONDict:
    text_section: JSONDict = {}
    if isinstance(existing_text, dict):
        text_section.update(existing_text)
    text_section["format"] = format_payload
    return text_section


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _process_stream_chunk(
    *,
    chunk: object,
    accumulated_text_parts: list[str],
    accumulated_tool_calls: list[JSONDict],
    accumulated_reasoning_parts: list[str],
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


def _coerce_to_json_dict(value: object | JSONValue) -> JSONDict | None:
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, dict):
            return converted
    return None


def _coerce_to_json_response(response: object) -> JSONDict | None:
    if isinstance(response, dict):
        return response
    return _coerce_to_json_dict(response)


def _ensure_json_dicts(value: object | JSONValue | None) -> list[JSONDict]:
    normalized: list[JSONDict] = []
    if value is None:
        return normalized
    if isinstance(value, list):
        for item in value:
            item_dict = item if isinstance(item, dict) else _coerce_to_json_dict(item)
            if item_dict is not None:
                normalized.append(item_dict)
        return normalized
    item_dict = _coerce_to_json_dict(value)
    if item_dict is not None:
        normalized.append(item_dict)
    return normalized


def _extract_responses_text(response: object) -> tuple[str, list[JSONDict] | None, str | None]:
    text_parts: list[str] = []
    tool_calls: list[JSONDict] = []
    reasoning_parts: list[str] = []

    payload = _coerce_to_json_response(response)
    if not payload:
        return "", None, None

    for output in _ensure_json_dicts(payload.get("output")):
        output_type = output.get("type")
        summary_blocks = output.get("summary")
        if summary_blocks:
            reasoning_parts.extend(_collect_text_blocks(summary_blocks))

        if output_type == "message":
            for part in _ensure_json_dicts(output.get("content")):
                if part.get("type") == "output_text":
                    text_value = part.get("text")
                    if isinstance(text_value, str) and text_value:
                        text_parts.append(text_value)
        elif output_type in {"function_call", "function"}:
            tool_calls.append(output)

    content = "\n".join(text_parts)
    reasoning_content = "\n".join(reasoning_parts) or None
    return content, tool_calls or None, reasoning_content


def _collect_text_blocks(blocks: object | JSONValue | None) -> list[str]:
    collected: list[str] = []
    if not blocks:
        return collected

    for block in _ensure_json_dicts(blocks):
        text_value = block.get("text")
        if isinstance(text_value, str) and text_value:
            collected.append(text_value)
    return collected


def _extract_finish_reason(response: object) -> str | None:
    try:
        payload = _coerce_to_json_response(response)
        if not payload:
            return None
        for choice in _ensure_json_dicts(payload.get("output")):
            if choice.get("type") == "message":
                metadata = choice.get("metadata")
                if isinstance(metadata, dict):
                    finish_reason = metadata.get("finish_reason")
                    if isinstance(finish_reason, str):
                        return finish_reason
        status_value = payload.get("status")
        return status_value if isinstance(status_value, str) else None
    except Exception:  # pragma: no cover - defensive
        return None


def _usage_to_dict(usage: object | JSONDict | None) -> JSONDict | None:
    if usage is None:
        return None
    return _coerce_to_json_dict(usage)


def _coerce_cached_tokens(value: JSONValue | None) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _is_cache_hit(usage: JSONDict | None) -> bool:
    if not usage:
        return False
    input_details = usage.get("input_tokens_details")
    if not isinstance(input_details, dict):
        return False
    return _coerce_cached_tokens(input_details.get("cached_tokens")) > 0


def _coerce_model(value: JSONValue | None) -> str | None:
    """Normalize model field into a string if present."""
    return value if isinstance(value, str) else None


__all__ = [
    "CAPABILITIES",
    "DoubaoResponsesAdapter",
    "_validate_extra_body",
    "send_request",
]
