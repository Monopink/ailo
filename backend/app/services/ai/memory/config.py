"""Memory configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMConfig
from app.type_defs import InstanceContext
from app.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MEMORY_LIMITS: dict[str, int] = {"core": 30, "recent": 50}
DEFAULT_MEMORY_BUDGET_TOKENS = 700
_VALID_TYPES = {"core", "recent"}


def _extract_limits(candidate: Mapping[str, object] | None) -> dict[str, int] | None:
    if not candidate:
        return None
    raw_limits = candidate.get("memory_limits")
    if not isinstance(raw_limits, Mapping):
        return None
    coerced: dict[str, int] = {}
    for key in _VALID_TYPES:
        value = raw_limits.get(key)
        if isinstance(value, bool):
            # bool is subclass of int, but semantically invalid here
            return None
        if isinstance(value, int | float):
            coerced[key] = int(value)
        else:
            return None
    if coerced["core"] <= 0 or coerced["recent"] <= 0:
        return None
    return coerced


def _clone_limits(limits: dict[str, int]) -> dict[str, int]:
    return {"core": int(limits["core"]), "recent": int(limits["recent"])}


def _extract_budget_tokens(candidate: Mapping[str, object] | None) -> int | None:
    if not candidate:
        return None
    raw_value = candidate.get("memory_budget_tokens")
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, int | float):
        value = int(raw_value)
    elif isinstance(raw_value, str):
        try:
            value = int(raw_value.strip())
        except ValueError:
            return None
    else:
        return None
    if value <= 0:
        return None
    return value


async def get_memory_limits(db: AsyncSession, context: InstanceContext) -> dict[str, int]:
    """Resolve memory limits for an instance using three-tier fallback."""

    request_params = context.get("request_params") or {}
    llm_config_id = context.get("llm_config_id")
    return await get_memory_limits_for_params(
        db,
        request_params=request_params if isinstance(request_params, Mapping) else {},
        llm_config_id=llm_config_id if isinstance(llm_config_id, int) else None,
    )


async def get_memory_limits_for_params(
    db: AsyncSession,
    *,
    request_params: Mapping[str, object] | None,
    llm_config_id: int | None,
) -> dict[str, int]:
    """Resolve memory limits from request params and llm config."""

    limits = _extract_limits(request_params)
    if limits:
        return _clone_limits(limits)

    if llm_config_id:
        config = await db.get(LLMConfig, llm_config_id)
        if config and config.extra_params:
            limits = _extract_limits(config.extra_params)
            if limits:
                return _clone_limits(limits)

    return _clone_limits(DEFAULT_MEMORY_LIMITS)


async def get_memory_budget_tokens(db: AsyncSession, context: InstanceContext) -> int:
    """Resolve memory budget tokens for an instance using three-tier fallback."""

    request_params = context.get("request_params") or {}
    llm_config_id = context.get("llm_config_id")
    return await get_memory_budget_tokens_for_params(
        db,
        request_params=request_params if isinstance(request_params, Mapping) else {},
        llm_config_id=llm_config_id if isinstance(llm_config_id, int) else None,
    )


async def get_memory_budget_tokens_for_params(
    db: AsyncSession,
    *,
    request_params: Mapping[str, object] | None,
    llm_config_id: int | None,
) -> int:
    """Resolve memory budget tokens from request params and llm config."""

    request_budget = _extract_budget_tokens(request_params)
    if request_budget is not None:
        return int(request_budget)

    if llm_config_id:
        config = await db.get(LLMConfig, llm_config_id)
        if config and config.extra_params:
            config_budget = _extract_budget_tokens(config.extra_params)
            if config_budget is not None:
                return int(config_budget)

    return DEFAULT_MEMORY_BUDGET_TOKENS
