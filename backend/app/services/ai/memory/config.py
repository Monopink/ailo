"""Memory configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMConfig
from app.services.ai.types import InstanceContext
from app.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MEMORY_LIMITS: dict[str, int] = {"core": 30, "recent": 50}
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


async def get_memory_limits(db: AsyncSession, context: InstanceContext) -> dict[str, int]:
    """Resolve memory limits for an instance using three-tier fallback."""

    request_params = context.get("request_params") or {}
    limits = _extract_limits(request_params)
    if limits:
        return _clone_limits(limits)

    llm_config_id = context.get("llm_config_id")
    if llm_config_id:
        config = await db.get(LLMConfig, llm_config_id)
        if config and config.extra_params:
            limits = _extract_limits(config.extra_params)
            if limits:
                return _clone_limits(limits)

    return _clone_limits(DEFAULT_MEMORY_LIMITS)
