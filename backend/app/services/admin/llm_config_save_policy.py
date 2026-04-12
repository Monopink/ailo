"""
Admin save policy for LLM configurations.

This module centralizes save-time rules that must be enforced when creating or
editing `llm_configs` via the admin panel.
"""

from __future__ import annotations

import time
from typing import Final

import jsonschema
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sqlalchemy_inspect

from app.models.llm import LLMConfig, LLMProvider
from app.services.llm.client import invoke_llm_with_explicit_config
from app.type_defs import JSONDict

_JSON_SCHEMA_RETEST_ATTRS: Final[tuple[str, ...]] = ("provider_id", "model_name", "extra_params")

_TEST_SCHEMA: JSONDict = {
    "type": "object",
    "properties": {"test_field": {"type": "string", "description": "A test field"}},
    "required": ["test_field"],
    "additionalProperties": False,
}

_TEST_MESSAGE: Final[str] = (
    "Please respond with a JSON object containing a test_field with value 'success'"
)


async def ensure_llm_config_json_schema_mode_on_save(
    session: AsyncSession,
    *,
    config: LLMConfig,
    is_create: bool,
) -> None:
    """
    Enforce JSON Schema verification rules for an LLMConfig object being saved.

    Rules:
    - Mock provider: always force `json_schema_mode='strict'` (no external probe).
    - Only Active (status=1) non-mock configs are probed.
    - On edit: probe again when key fields change or when activating an Inactive config.
    - Probe failure rejects the save (raise a ValueError with an English message).
    """
    provider_obj = getattr(config, "provider", None)
    if isinstance(provider_obj, LLMProvider) and getattr(provider_obj, "id", None) is not None:
        provider = provider_obj
    else:
        provider = await _load_provider(session, provider_id=getattr(config, "provider_id", None))
    provider_name = provider.name

    if provider_name == "mock":
        config.json_schema_mode = "strict"
        return

    status_value = _coerce_int(getattr(config, "status", 1), default=1)
    if status_value != 1:
        if is_create and getattr(config, "json_schema_mode", None) in (None, ""):
            config.json_schema_mode = "auto"
        return

    should_probe = True if is_create else _should_probe_on_edit(config)
    if not should_probe:
        return

    probe = await probe_json_schema_support_for_draft(
        config=config,
        provider=provider,
    )
    if not bool(probe.get("success")):
        message = str(probe.get("message") or "JSON Schema verification failed")
        raise ValueError(message)

    config.json_schema_mode = "strict"


async def probe_json_schema_support_for_draft(
    *,
    config: LLMConfig,
    provider: LLMProvider,
) -> JSONDict:
    """
    Probe whether the given config+provider can produce a valid JSON object under a fixed schema.

    This function does not mutate or commit database state.
    """
    test_messages: list[JSONDict] = [{"role": "user", "content": _TEST_MESSAGE}]
    start_time = time.perf_counter()
    try:
        llm_result = await invoke_llm_with_explicit_config(
            config=config,
            provider=provider,
            messages=test_messages,
            json_schema=_TEST_SCHEMA,
            temperature=0.7,
            max_tokens=100,
            thinking_mode="disabled",
        )
    except Exception as exc:
        response_time_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "success": False,
            "message": f"JSON Schema probe request failed: {exc!s}",
            "provider": provider.name,
            "config_name": config.name,
            "response_time_ms": response_time_ms,
        }

    response_time_ms = int((time.perf_counter() - start_time) * 1000)
    response_payload = llm_result.get("response")

    if not bool(llm_result.get("success")):
        error_msg = llm_result.get("error") or llm_result.get("error_code") or "Unknown error"
        return {
            "success": False,
            "message": f"JSON Schema probe failed: {error_msg}",
            "provider": provider.name,
            "config_name": config.name,
            "model": llm_result.get("model") or config.model_name or provider.default_model,
            "response_time_ms": response_time_ms,
        }

    if not isinstance(response_payload, dict):
        return {
            "success": False,
            "message": "JSON Schema probe failed: response is not a JSON object",
            "provider": provider.name,
            "config_name": config.name,
            "model": llm_result.get("model") or config.model_name or provider.default_model,
            "response_time_ms": response_time_ms,
        }

    try:
        jsonschema.validate(instance=response_payload, schema=_TEST_SCHEMA)
    except Exception as exc:
        return {
            "success": False,
            "message": f"JSON Schema probe failed: invalid response payload ({exc!s})",
            "provider": provider.name,
            "config_name": config.name,
            "model": llm_result.get("model") or config.model_name or provider.default_model,
            "response_time_ms": response_time_ms,
        }

    return {
        "success": True,
        "message": "JSON Schema is supported",
        "provider": provider.name,
        "config_name": config.name,
        "model": llm_result.get("model") or config.model_name or provider.default_model,
        "usage": llm_result.get("usage") if isinstance(llm_result.get("usage"), dict) else {},
        "response_time_ms": response_time_ms,
    }


def _should_probe_on_edit(obj: LLMConfig) -> bool:
    state = sqlalchemy_inspect(obj)

    if "status" in state.attrs and state.attrs["status"].history.has_changes():
        added = state.attrs["status"].history.added
        if added and _coerce_int(added[0], default=None) == 1:
            return True

    for attr_name in _JSON_SCHEMA_RETEST_ATTRS:
        if attr_name in state.attrs and state.attrs[attr_name].history.has_changes():
            return True

    return getattr(obj, "json_schema_mode", None) in (None, "auto")


async def _load_provider(session: AsyncSession, *, provider_id: int | None) -> LLMProvider:
    if provider_id is None:
        raise ValueError("Provider is required")
    try:
        resolved_provider_id = int(provider_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Provider is required") from exc

    result = await session.execute(
        select(LLMProvider).where(LLMProvider.id == resolved_provider_id)
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise ValueError("Provider not found for this configuration")
    return provider


def _coerce_int(value: object, *, default: int | None) -> int | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return default
