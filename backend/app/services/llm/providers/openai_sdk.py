"""
OpenAI-compatible provider adapter (Responses API only).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from models.llm import LLMConfig, LLMProvider
from services.llm.types import LLMRequestOptions, LLMProviderResult
from exceptions.llm import LLMConfigurationError, LLMRequestError, LLMTimeoutError
from utils.logging import get_logger

logger = get_logger(__name__)


async def send_request(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    *,
    stream: bool = False,
    preemption_checker=None,
) -> LLMProviderResult:
    """
    Dispatch the request to Doubao/OpenAI Responses API.
    """
    return await _send_responses_request(
        config=config,
        provider=provider,
        options=options,
        stream=stream,
        preemption_checker=preemption_checker,
    )


# ---------------------------------------------------------------------------
# Responses API
# ---------------------------------------------------------------------------


async def _send_responses_request(
    config: LLMConfig,
    provider: LLMProvider,
    options: LLMRequestOptions,
    *,
    stream: bool,
    preemption_checker,
) -> LLMProviderResult:
    client = _build_client(
        provider, timeout=options.provider_overrides.get("timeout") or options.max_tokens
    )

    params = _build_responses_params(options)
    request_kwargs = _build_request_kwargs(options)

    try:
        if stream:
            return await _stream_responses_request(
                client=client,
                params=params,
                request_kwargs=request_kwargs,
                options=options,
                preemption_checker=preemption_checker,
            )

        response = await client.responses.create(**params, **request_kwargs)
        content, tool_calls, reasoning_content = _extract_responses_text(response)
        usage = _usage_to_dict(getattr(response, "usage", None))

        return LLMProviderResult(
            content=content,
            model=response.model,
            usage=usage,
            finish_reason=_extract_finish_reason(response),
            raw_response=response.to_dict(),
            request_params=params,
            response_id=getattr(response, "id", None),
            cache_hit=_is_cache_hit(usage),
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
        )

    except LLMTimeoutError:
        raise
    except LLMRequestError:
        raise
    except Exception as exc:
        logger.error("responses_request_failed", error=str(exc), exc_info=True)
        raise LLMRequestError(provider=provider.name, message=str(exc)) from exc


async def _stream_responses_request(
    client: AsyncOpenAI,
    params: Dict[str, Any],
    request_kwargs: Dict[str, Any],
    options: LLMRequestOptions,
    preemption_checker,
) -> LLMProviderResult:
    """
    Stream responses using Doubao Responses API.

    IMPORTANT: Based on Doubao official documentation and expert confirmation:
    - Pass stream=True as a direct parameter to create(), NOT in extra_body
    - response_id is returned in the first chunk
    - usage info is returned in the last chunk
    - Stream ends with data: [DONE] marker
    - Iterate chunks directly without relying on OpenAI SDK's internal state machine
    """
    call_kwargs = dict(request_kwargs)

    # Accumulate response data from stream chunks
    accumulated_text_parts: List[str] = []
    accumulated_tool_calls: List[Dict[str, Any]] = []
    accumulated_reasoning_parts: List[str] = []
    final_model = params["model"]
    final_usage: Optional[Dict[str, Any]] = None
    final_response_id: Optional[str] = None
    final_finish_reason: Optional[str] = None

    try:
        # CRITICAL: stream=True must be a direct parameter, NOT in extra_body
        # When in extra_body, SDK returns a string instead of stream object
        stream = await client.responses.create(**params, **call_kwargs, stream=True)

        logger.debug("stream_started", model=params["model"])
        chunk_count = 0

        async for chunk in stream:
            chunk_count += 1

            # Log first few chunks in detail for debugging
            if chunk_count <= 3:
                try:
                    chunk_dict = chunk.to_dict() if hasattr(chunk, 'to_dict') else str(chunk)
                    logger.info(
                        "stream_chunk_detail",
                        chunk_number=chunk_count,
                        chunk_structure=chunk_dict
                    )
                except Exception as e:
                    logger.warning(
                        "stream_chunk_serialization_failed",
                        chunk_number=chunk_count,
                        error=str(e)
                    )

            logger.debug("stream_chunk_received",
                        chunk_number=chunk_count,
                        has_output=hasattr(chunk, 'output'),
                        output_is_none=getattr(chunk, 'output', None) is None,
                        chunk_type=type(chunk).__name__)

            # Check for preemption
            if preemption_checker and await preemption_checker():
                logger.info("stream_preempted", chunks_processed=chunk_count)
                return LLMProviderResult(
                    content=None,
                    model=final_model,
                    usage=None,
                    finish_reason="preempted",
                    raw_response=None,
                    request_params=params,
                    preempted=True,
                )

            # Extract response_id (usually in first chunk)
            if hasattr(chunk, 'id') and chunk.id:
                final_response_id = chunk.id
                logger.debug("stream_response_id_captured", response_id=final_response_id)

            # Extract model
            if hasattr(chunk, 'model') and chunk.model:
                final_model = chunk.model

            # Extract usage (in last chunk according to Doubao expert)
            if hasattr(chunk, 'usage') and chunk.usage:
                final_usage = _usage_to_dict(chunk.usage)
                logger.debug("stream_usage_captured", usage=final_usage)

            # Extract status/finish_reason
            if hasattr(chunk, 'status') and chunk.status:
                final_finish_reason = chunk.status

            # Extract output content (handle null output gracefully)
            output_list = getattr(chunk, 'output', None)
            if output_list:
                for output in output_list:
                    output_type = getattr(output, "type", None)
                    logger.debug("stream_output_processing", output_type=output_type)

                    # Extract reasoning/summary
                    summary_blocks = getattr(output, "summary", None)
                    if summary_blocks:
                        accumulated_reasoning_parts.extend(_collect_text_blocks(summary_blocks))

                    # Extract message content
                    if output_type == "message":
                        content_blocks = getattr(output, "content", None)
                        if content_blocks:
                            for part in content_blocks:
                                if getattr(part, "type", None) == "output_text":
                                    text = getattr(part, "text", None)
                                    if text:
                                        accumulated_text_parts.append(text)
                                        logger.debug("stream_text_accumulated",
                                                    text_length=len(text),
                                                    total_parts=len(accumulated_text_parts))

                    # Extract tool calls
                    elif output_type in {"function_call", "function"}:
                        try:
                            accumulated_tool_calls.append(output.to_dict())
                        except AttributeError:
                            accumulated_tool_calls.append({"type": output_type})

        # Build final response from accumulated data
        content = "".join(accumulated_text_parts)
        reasoning_content = "\n".join(filter(None, accumulated_reasoning_parts)) or None

        logger.info("stream_completed",
                   chunks_processed=chunk_count,
                   text_parts_count=len(accumulated_text_parts),
                   final_content_length=len(content),
                   has_usage=final_usage is not None,
                   has_response_id=final_response_id is not None)

        if not content and not accumulated_tool_calls:
            logger.warning("stream_empty_response",
                          chunks_processed=chunk_count,
                          final_model=final_model,
                          final_usage=final_usage)

        return LLMProviderResult(
            content=content,
            model=final_model,
            usage=final_usage,
            finish_reason=final_finish_reason or "completed",
            raw_response=None,  # No single final response object in streaming
            request_params=params,
            response_id=final_response_id,
            cache_hit=_is_cache_hit(final_usage),
            tool_calls=accumulated_tool_calls or None,
            reasoning_content=reasoning_content,
        )

    except Exception as exc:
        logger.error("stream_responses_failed", error=str(exc), exc_info=True)
        raise LLMRequestError(provider="doubao", message=f"Streaming failed: {str(exc)}") from exc


def _build_responses_params(options: LLMRequestOptions) -> Dict[str, Any]:
    """
    Build parameters for Responses API.

    IMPORTANT: Responses API has VERY LIMITED parameter support compared to Chat Completions API.
    Based on official Doubao documentation, ONLY these parameters are supported:
    - model (required)
    - input (required)
    - previous_response_id (optional, for context chaining)

    All other parameters (temperature, top_p, tools, thinking, text.format, etc.)
    must be passed via extra_body, NOT as direct parameters.
    """
    params: Dict[str, Any] = {
        "model": options.model,
        "input": _convert_messages_to_input(options.messages),
    }

    # previous_response_id is supported as direct parameter (for caching)
    if options.caching.previous_response_id:
        params["previous_response_id"] = options.caching.previous_response_id

    model_override = options.provider_overrides.get("model_override") or options.provider_overrides.get(
        "model"
    )
    if isinstance(model_override, str):
        params["model"] = model_override

    manual_params = options.provider_overrides.get("params_override")
    if isinstance(manual_params, dict):
        params.update(manual_params)

    return params


def _build_request_kwargs(options: LLMRequestOptions) -> Dict[str, Any]:
    """
    Build extra_body and other request kwargs for Responses API.

    ALL optional parameters must go in extra_body for Responses API:
    - temperature, top_p, max_tokens
    - tools, tool_choice
    - thinking
    - caching
    - text.format (JSON schema / json_object)
    """
    extra_body = dict(options.extra_body or {})

    # Add temperature and top_p to extra_body
    if options.temperature is not None:
        extra_body["temperature"] = options.temperature
    if options.top_p is not None:
        extra_body["top_p"] = options.top_p

    # Add max_tokens to extra_body
    if options.max_tokens is not None:
        extra_body["max_output_tokens"] = options.max_tokens

    # Add stop sequences to extra_body
    if options.stop_sequences:
        extra_body["stop"] = options.stop_sequences

    # Add tools to extra_body
    if options.tools:
        extra_body["tools"] = options.tools
        if options.tool_choice:
            extra_body["tool_choice"] = options.tool_choice
        if options.max_tool_calls:
            extra_body["max_tool_calls"] = options.max_tool_calls

    # Add JSON schema to extra_body through text.format
    text_format_payload: Optional[Dict[str, Any]] = None
    if options.json_schema:
        text_format_payload = _build_json_schema_format(options.json_schema)

    if text_format_payload:
        extra_body["text"] = _merge_text_format(extra_body.get("text"), text_format_payload)

    # Add caching configuration to extra_body
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

    request_kwargs: Dict[str, Any] = {
        "extra_headers": merged_headers or None,
        "extra_query": merged_query or None,
        "extra_body": extra_body or None,
        "timeout": options.provider_overrides.get("timeout"),
    }

    return request_kwargs


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
    """
    Merge the new format payload into existing text config (if any).
    """
    text_section: Dict[str, Any] = {}
    if isinstance(existing_text, dict):
        text_section.update(existing_text)
    text_section["format"] = format_payload
    return text_section


def _convert_messages_to_input(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    converted = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")

        if isinstance(content, list):
            content_blocks = content
        else:
            content_blocks = [
                {
                    "type": "input_text",
                    "text": str(content),
                }
            ]

        converted.append({"role": role, "content": content_blocks})

    return converted


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
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _build_client(provider: LLMProvider, timeout: Optional[int]) -> AsyncOpenAI:
    api_key = _get_api_key(provider)
    if not api_key:
        raise LLMConfigurationError(
            f"API key not configured for provider: {provider.display_name}. "
            f"Please set environment variable: {provider.api_key_env or f'{provider.name.upper()}_API_KEY'}"
        )

    return AsyncOpenAI(
        base_url=provider.base_url,
        api_key=api_key,
        timeout=timeout or 60,
        max_retries=3,
    )


def _get_api_key(provider: LLMProvider) -> Optional[str]:
    if provider.api_key_env:
        api_key = os.getenv(provider.api_key_env)
        if api_key:
            return api_key

    default_env_name = f"{provider.name.upper()}_API_KEY"
    return os.getenv(default_env_name)


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
