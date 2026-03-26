"""
Unified LLM client interface built on the Responses API.

This module centralizes request construction (tools, caching, overrides) and
delegates transport details to provider adapters.
"""

from __future__ import annotations

import json
import time
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.llm import (
    ConfigNotVerifiedError,
    JSONSchemaNotSupportedError,
    LLMConfigurationError,
    LLMNoConfigError,
    LLMRequestError,
    LLMResponseFormatError,
    LLMTimeoutError,
)
from app.models.llm import LLMConfig, LLMProvider
from app.type_defs import (
    JSONDict,
    JSONValue,
    LLMCachingOptions,
    LLMRequestOptions,
    LLMRequestPayload,
    LLMRequestPayloadCaching,
    LLMSessionContext,
    LLMStreamingDecision,
    PreemptionChecker,
    ProviderTool,
)
from app.utils.logging import get_logger

from .config import get_active_configs, get_config_by_provider, get_llm_config, get_primary_config
from .providers import factory
from .streaming_policy import extract_stream_override, resolve_streaming_decision
from .utils import is_valid_json

logger = get_logger(__name__)

MAX_FALLBACK_PRIORITY = 99


async def invoke_llm(
    db: AsyncSession,
    messages: list[JSONDict],
    json_schema: JSONDict | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    thinking_mode: str | None = None,
    name: str | None = None,
    instance_request_params: JSONDict | None = None,
    preemption_checker: PreemptionChecker | None = None,
    session_context: LLMSessionContext | None = None,
) -> JSONDict:
    """
    Send an LLM invocation request with automatic provider selection/failover.

    Args:
        db: Database session.
        messages: Conversation messages (role/content).
        json_schema: Optional JSON schema for structured responses.
        temperature: Explicit temperature override.
        max_tokens: Explicit max tokens override.
        thinking_mode: Explicit thinking mode override.
        name: LLM config name (defaults to primary).
        instance_request_params: Per-instance overrides (tools, caching, etc.).
        preemption_checker: Optional async callback to stop streaming early.
        session_context: Conversation identifiers (user+instance) used for caching.
    """
    try:
        configs_to_try = await _get_configs_to_try(db, name)

        if not configs_to_try:
            raise LLMNoConfigError(config_name=name, details={"requested_name": name})

        last_error = None
        last_error_code = None

        for config, provider in configs_to_try:
            try:
                result = await _call_provider(
                    config=config,
                    provider=provider,
                    messages=messages,
                    json_schema=json_schema,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    thinking_mode=thinking_mode,
                    instance_request_params=instance_request_params,
                    preemption_checker=preemption_checker,
                    session_context=session_context,
                )

                if isinstance(result, dict):
                    result.setdefault(
                        "config_used",
                        {
                            "id": config.id,
                            "name": config.name,
                            "provider_name": provider.name,
                            "model": config.model_name or provider.default_model,
                        },
                    )

                if result["success"]:
                    result["config_used"] = {
                        "id": config.id,
                        "name": config.name,
                        "provider_name": provider.name,
                        "model": config.model_name or provider.default_model,
                    }
                    if "request_payload" not in result:
                        result["request_payload"] = None
                    return result

                last_error = result.get("error", "Unknown error")
                last_error_code = result.get("error_code", "UNKNOWN")
                logger.warning(
                    "llm_config_failed",
                    config_name=config.name,
                    provider=provider.name,
                    error=last_error,
                    error_code=last_error_code,
                )

            except Exception as exc:
                last_error = str(exc)
                last_error_code = getattr(exc, "error_code", "EXCEPTION")
                logger.error(
                    "llm_config_exception",
                    config_name=config.name,
                    provider=provider.name,
                    error=last_error,
                    exc_info=True,
                )

        return {
            "success": False,
            "error": f"All LLM configurations failed. Last error: {last_error}",
            "error_code": last_error_code or "ALL_CONFIGS_FAILED",
            "response": None,
            "usage": None,
            "request_payload": None,
        }

    except LLMNoConfigError as exc:
        logger.error("no_llm_config", config_name=name)
        return {
            "success": False,
            "error": str(exc),
            "error_code": exc.error_code,
            "response": None,
            "usage": None,
            "request_payload": None,
        }


async def invoke_llm_with_provider(
    db: AsyncSession,
    provider_name: str,
    messages: list[JSONDict],
    json_schema: JSONDict | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    thinking_mode: str | None = None,
    instance_request_params: JSONDict | None = None,
    preemption_checker: PreemptionChecker | None = None,
    session_context: LLMSessionContext | None = None,
) -> JSONDict:
    """Send an LLM invocation request to a specific provider."""

    config_result = await get_config_by_provider(db, provider_name)

    if not config_result:
        return {
            "success": False,
            "error": f"{provider_name.title()} configuration not found or inactive",
            "response": None,
            "usage": None,
            "request_payload": None,
        }

    config, provider = config_result
    return await _call_provider(
        config=config,
        provider=provider,
        messages=messages,
        json_schema=json_schema,
        temperature=temperature,
        max_tokens=max_tokens,
        thinking_mode=thinking_mode,
        instance_request_params=instance_request_params,
        preemption_checker=preemption_checker,
        session_context=session_context,
    )


async def select_config_for_ai(
    db: AsyncSession,
    name: str | None = None,
) -> tuple[LLMConfig, LLMProvider]:
    """
    Select and validate LLM config for AI Instance usage.

    Ensures the selected config supports JSON Schema.
    """

    if name:
        config_result = await get_llm_config(db, name)
        if not config_result:
            raise LLMNoConfigError(
                config_name=name,
                message=f"配置 '{name}' 不存在或未激活",
                details={"requested_name": name},
            )
    else:
        config_result = await get_primary_config(db)
        if not config_result:
            raise LLMNoConfigError(
                message="没有可用的主配置",
                details={"requested_name": "primary"},
            )

    config, provider = config_result

    if config.json_schema_mode == "auto":
        raise ConfigNotVerifiedError(config_name=config.name)

    if config.json_schema_mode == "disabled":
        raise JSONSchemaNotSupportedError(config_name=config.name)

    logger.info(
        "config_selected_for_ai",
        config_name=config.name,
        provider=provider.name,
        json_schema_mode=config.json_schema_mode,
    )

    return config, provider


async def validate_ai_response(
    db: AsyncSession,
    config: LLMConfig,
    response_content: str,
    allow_auto_update: bool = True,
) -> None:
    """
    Validate AI response format and optionally auto-update config if needed.
    """
    is_json, _ = is_valid_json(response_content)

    if not is_json:
        logger.error(
            "ai_response_format_error",
            config_name=config.name,
            json_schema_mode=config.json_schema_mode,
            response_preview=response_content[:200],
            allow_auto_update=allow_auto_update,
        )

        old_mode = config.json_schema_mode
        if allow_auto_update and config.json_schema_mode != "disabled":
            config.json_schema_mode = "disabled"
            await db.commit()

            logger.warning(
                "config_auto_updated_to_disabled",
                config_name=config.name,
                old_mode=old_mode,
                new_mode="disabled",
            )

        raise LLMResponseFormatError(
            config_name=config.name,
            details={
                "response_preview": response_content[:200],
                "old_json_schema_mode": old_mode,
                "auto_update_allowed": allow_auto_update,
            },
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _call_provider(
    config: LLMConfig,
    provider: LLMProvider,
    messages: list[JSONDict],
    json_schema: JSONDict | None,
    temperature: float | None,
    max_tokens: int | None,
    thinking_mode: str | None,
    instance_request_params: JSONDict | None,
    preemption_checker: PreemptionChecker | None,
    session_context: LLMSessionContext | None,
) -> JSONDict:
    session_meta: dict[str, str] = {}
    if session_context:
        session_meta = {
            "session_user_qiao_id": session_context.user_qiao_id,
            "session_instance_qiao_id": session_context.instance_qiao_id,
        }
    start_time = time.perf_counter()
    try:
        overrides = instance_request_params if isinstance(instance_request_params, dict) else {}
        options = await _build_request_options(
            config=config,
            provider=provider,
            messages=messages,
            json_schema=json_schema,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking_mode=thinking_mode,
            instance_request_params=overrides,
        )

        stream_override = extract_stream_override(overrides)
        decision = resolve_streaming_decision(
            config=config,
            provider=provider,
            enable_override=stream_override,
            has_preemption_checker=preemption_checker is not None,
        )
        use_stream = decision.should_stream

        try:
            provider_result = await factory.send_request(
                config=config,
                provider=provider,
                options=options,
                stream=use_stream,
                preemption_checker=preemption_checker,
            )
        except (LLMTimeoutError, LLMRequestError) as exc:
            elapsed = time.perf_counter() - start_time
            request_payload = cast(
                JSONDict,
                _build_request_payload(options=options, decision=decision),
            )
            return {
                "success": False,
                "error": str(exc),
                "error_code": getattr(exc, "error_code", "LLM_REQUEST_ERROR"),
                "response": None,
                "usage": None,
                "model": options.model,
                "response_time": elapsed,
                "request_payload": request_payload,
                "streaming": _format_streaming_metadata(decision),
            }

        if provider_result.preempted:
            elapsed = time.perf_counter() - start_time
            return {
                "success": False,
                "preempted": True,
                "error": "LLM request preempted by new message",
                "usage": provider_result.usage,
                "request_payload": provider_result.request_params,
                "streaming": _format_streaming_metadata(decision),
                "response_time": elapsed,
            }

        # Parse JSON response if json_schema was provided
        response_content = provider_result.content
        if json_schema and isinstance(response_content, str):
            try:
                response_content = json.loads(response_content)
            except (json.JSONDecodeError, ValueError):
                # Keep as string if parsing fails (will be caught by validation)
                pass

        elapsed = time.perf_counter() - start_time
        return {
            "success": True,
            "response": response_content,
            "raw_content": provider_result.content
            if isinstance(provider_result.content, str)
            else None,
            "usage": provider_result.usage,
            "finish_reason": provider_result.finish_reason,
            "model": provider_result.model,
            "raw_response": provider_result.raw_response,
            "request_payload": provider_result.request_params,
            "response_id": provider_result.response_id,
            "cache_hit": provider_result.cache_hit,
            "tool_calls": [dict(tool_call) for tool_call in provider_result.tool_calls]
            if provider_result.tool_calls
            else None,
            "cache_strategy": options.caching.strategy,
            "reasoning_content": provider_result.reasoning_content,
            "streaming": _format_streaming_metadata(decision),
            "response_time": elapsed,
        }

    except Exception as exc:
        logger.error(
            "llm_unexpected_error",
            config_name=config.name,
            provider=provider.name,
            error=str(exc),
            exc_info=True,
            **session_meta,
        )
        raise


async def _build_request_options(
    config: LLMConfig,
    provider: LLMProvider,
    messages: list[JSONDict],
    json_schema: JSONDict | None,
    temperature: float | None,
    max_tokens: int | None,
    thinking_mode: str | None,
    instance_request_params: JSONDict | None,
) -> LLMRequestOptions:
    overrides = instance_request_params if isinstance(instance_request_params, dict) else {}

    resolved_temperature = (
        float(temperature)
        if temperature is not None
        else _extract_float(overrides, "temperature", default=_to_float(config.temperature, 0.7))
    )
    resolved_max_tokens = (
        int(max_tokens)
        if max_tokens is not None
        else _extract_int(overrides, "max_tokens", default=config.max_tokens or 4000)
    )
    override_thinking = overrides.get("thinking_mode")
    if thinking_mode is not None:
        thinking_mode_input = thinking_mode
    elif isinstance(override_thinking, str):
        thinking_mode_input = override_thinking
    else:
        thinking_mode_input = config.thinking_mode
    resolved_thinking_mode = _normalize_thinking_mode(
        thinking_mode_input,
        config_name=config.name,
    )
    resolved_top_p = _extract_float(overrides, "top_p", default=_to_float(config.top_p, 0.7))
    resolved_frequency_penalty = _extract_float(
        overrides, "frequency_penalty", default=_to_float(config.frequency_penalty, 0.0)
    )
    resolved_presence_penalty = _extract_float(
        overrides, "presence_penalty", default=_to_float(config.presence_penalty, 0.0)
    )

    resolved_stop_sequences: list[str] | None = None
    override_stops = overrides.get("stop_sequences")
    if isinstance(override_stops, list):
        resolved_stop_sequences = [str(item) for item in override_stops][:4]
    elif config.stop_sequences:
        resolved_stop_sequences = list(config.stop_sequences)

    tools: list[ProviderTool] = []
    tools_override = overrides.get("tools")
    if isinstance(tools_override, list):
        tools = [tool for tool in tools_override if isinstance(tool, dict)]
    else:
        config_tools = config.default_tools or []
        tools = [tool for tool in config_tools if isinstance(tool, dict)]

    tool_choice_override = overrides.get("tool_choice")
    tool_choice = (
        tool_choice_override
        if isinstance(tool_choice_override, str)
        else config.default_tool_choice
    ) or "auto"

    parallel_tool_calls_override = overrides.get("parallel_tool_calls")
    if isinstance(parallel_tool_calls_override, bool):
        parallel_tool_calls = parallel_tool_calls_override
    else:
        parallel_tool_calls = bool(config.parallel_tool_calls)

    max_tool_calls_override = overrides.get("max_tool_calls")
    if isinstance(max_tool_calls_override, int):
        max_tool_calls_value = max_tool_calls_override
    elif isinstance(max_tool_calls_override, float):
        max_tool_calls_value = int(max_tool_calls_override)
    else:
        max_tool_calls_value = config.max_tool_calls

    extra_headers = _normalize_str_dict(config.default_extra_headers)
    override_headers = overrides.get("default_extra_headers")
    if isinstance(override_headers, dict):
        extra_headers.update(_normalize_str_dict(override_headers))

    extra_query = _normalize_str_dict(config.default_extra_query)
    override_query = overrides.get("default_extra_query")
    if isinstance(override_query, dict):
        extra_query.update(_normalize_str_dict(override_query))

    extra_body: JSONDict = {}
    override_body = overrides.get("extra_body")
    if isinstance(override_body, dict):
        extra_body.update(override_body)

    provider_overrides = overrides.get("provider_overrides")
    if not isinstance(provider_overrides, dict):
        provider_overrides = {}

    caching_override = overrides.get("caching")
    caching_options = _build_caching_options(
        caching_override if isinstance(caching_override, dict) else None,
    )

    return LLMRequestOptions(
        model=config.model_name or provider.default_model or "",
        messages=messages,
        json_schema=json_schema,
        temperature=resolved_temperature,
        max_tokens=resolved_max_tokens,
        thinking_mode=resolved_thinking_mode,
        top_p=resolved_top_p,
        frequency_penalty=resolved_frequency_penalty,
        presence_penalty=resolved_presence_penalty,
        stop_sequences=resolved_stop_sequences,
        tools=tools,
        tool_choice=tool_choice,
        parallel_tool_calls=parallel_tool_calls,
        max_tool_calls=max_tool_calls_value,
        extra_headers=extra_headers,
        extra_query=extra_query,
        extra_body=extra_body,
        caching=caching_options,
        provider_overrides=provider_overrides,
    )


def _build_caching_options(
    override: JSONDict | None,
) -> LLMCachingOptions:
    """Caching is disabled globally; allow explicit override for testing only."""

    enabled = False
    strategy = "none"
    ttl_seconds: int | None = None
    previous_response_id: str | None = None

    if isinstance(override, dict):
        enabled_value = override.get("enabled")
        if isinstance(enabled_value, bool):
            enabled = enabled_value
        elif isinstance(enabled_value, int | float):
            enabled = bool(enabled_value)

        strategy_value = override.get("strategy")
        if isinstance(strategy_value, str) and strategy_value:
            strategy = strategy_value

        ttl_value = override.get("ttl_seconds")
        if isinstance(ttl_value, int | float):
            ttl_seconds = int(ttl_value)
        elif isinstance(ttl_value, str):
            try:
                ttl_seconds = int(ttl_value)
            except ValueError:
                ttl_seconds = None

        previous_response_id_value = override.get("previous_response_id")
        if isinstance(previous_response_id_value, str):
            previous_response_id = previous_response_id_value

    if not enabled:
        strategy = "none"
        ttl_seconds = None

    return LLMCachingOptions(
        enabled=enabled,
        strategy=strategy,
        ttl_seconds=ttl_seconds,
        previous_response_id=previous_response_id,
    )


def _normalize_str_dict(payload: JSONDict | dict[str, object] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    if not isinstance(payload, dict):
        return normalized
    for key, value in payload.items():
        if key is None or value is None:
            continue
        normalized[str(key)] = str(value)
    return normalized


def _normalize_thinking_mode(value: str | None, *, config_name: str) -> str:
    """
    Normalize thinking mode into a strict 3-state value expected by adapters.
    """
    if not isinstance(value, str):
        raise LLMConfigurationError(
            f"Missing thinking_mode for config '{config_name}'. "
            "Allowed values: enabled/disabled/auto."
        )

    normalized = value.strip().lower()
    if normalized in {"enabled", "disabled", "auto"}:
        return normalized

    raise LLMConfigurationError(
        f"Unknown thinking_mode '{value}' for config '{config_name}'. "
        "Allowed values: enabled/disabled/auto."
    )


async def _get_configs_to_try(
    db: AsyncSession,
    name: str | None,
) -> list[tuple[LLMConfig, LLMProvider]]:
    if name:
        config_result = await get_llm_config(db, name)
        return [config_result] if config_result else []

    return await get_active_configs(db, max_priority=MAX_FALLBACK_PRIORITY)


def _format_streaming_metadata(decision: LLMStreamingDecision) -> JSONDict:
    return {
        "requested": decision.requested,
        "used": decision.should_stream,
        "reason": decision.reason,
        "override_applied": decision.override_applied,
    }


def _build_request_payload(
    *,
    options: LLMRequestOptions,
    decision: LLMStreamingDecision,
) -> LLMRequestPayload:
    messages_payload: list[JSONValue] = [dict(message) for message in options.messages]
    tools_payload: list[JSONValue] = [dict(tool) for tool in options.tools]
    stop_sequences_payload: list[JSONValue] | None = None
    if options.stop_sequences is not None:
        stop_sequences_payload = [str(sequence) for sequence in options.stop_sequences]

    extra_headers_payload: JSONDict = dict(options.extra_headers)
    extra_query_payload: JSONDict = dict(options.extra_query)
    caching_payload: LLMRequestPayloadCaching = {
        "enabled": options.caching.enabled,
        "strategy": options.caching.strategy,
        "ttl_seconds": options.caching.ttl_seconds,
        "previous_response_id": options.caching.previous_response_id,
    }

    return {
        "model": options.model,
        "messages": messages_payload,
        "json_schema": options.json_schema,
        "temperature": options.temperature,
        "max_tokens": options.max_tokens,
        "thinking_mode": options.thinking_mode,
        "top_p": options.top_p,
        "frequency_penalty": options.frequency_penalty,
        "presence_penalty": options.presence_penalty,
        "stop_sequences": stop_sequences_payload,
        "tools": tools_payload,
        "tool_choice": options.tool_choice,
        "parallel_tool_calls": options.parallel_tool_calls,
        "max_tool_calls": options.max_tool_calls,
        "extra_headers": extra_headers_payload,
        "extra_query": extra_query_payload,
        "extra_body": options.extra_body,
        "caching": caching_payload,
        "provider_overrides": options.provider_overrides,
        "streaming": _format_streaming_metadata(decision),
    }


def _extract_float(source: JSONDict, key: str, default: float | None) -> float | None:
    value = source.get(key)
    if isinstance(value, int | float):
        return float(value)
    return default


def _extract_int(source: JSONDict, key: str, default: int | None) -> int | None:
    value = source.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _to_float(value: str | float | int | None, default: float | None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
