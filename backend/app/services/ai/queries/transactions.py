"""
Database transaction operations for AI services.

This module provides complex transaction operations that involve multiple
database operations and require atomicity.
"""

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIRequestLog
from app.type_defs import InstanceContext
from app.utils.logging import get_logger

from .instance_queries import get_user_id_by_qiao_id

logger = get_logger(__name__)

SENSITIVE_REQUEST_KEYS = {
    "authorization",
    "proxy-authorization",
    "api_key",
    "apikey",
    "api-key",
    "x-api-key",
    "x_api_key",
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "secret",
    "signature",
}


async def save_ai_request_log(
    db: AsyncSession,
    instance_context: InstanceContext,
    user_qiao_id: str,
    ai_response: object,
    llm_result: Mapping[str, object],
    buffer_id: int | None,
) -> int | None:
    """
    Save AI request log with correct field mapping.

    This fixes the field name bug: user_qiao_id (str) -> user_id (int)

    Args:
        db: Database session
        instance_context: Instance context dictionary
        user_qiao_id: User's qiao_id
        ai_response: AI response dictionary
        llm_result: LLM result with usage info
    """
    try:
        # Get user_id from user_qiao_id (FIX: was using user_qiao_id directly)
        user_id = await get_user_id_by_qiao_id(db, user_qiao_id)
        if not user_id:
            logger.warning("user_not_found_for_log", user_qiao_id=user_qiao_id)
            return None

        response_payload = _coerce_response_payload(ai_response)

        llm_debug_payload: dict[str, object] = {}
        for key in (
            "raw_response",
            "raw_content",
            "tool_calls",
            "reasoning_content",
            "finish_reason",
            "streaming",
        ):
            value = llm_result.get(key)
            if value not in (None, {}, []):
                llm_debug_payload[key] = value

        # Include cache metadata for debugging if provided.
        for meta_key in ("cache_hit", "cache_strategy"):
            if meta_key in llm_result and llm_result[meta_key] is not None:
                llm_debug_payload[meta_key] = llm_result[meta_key]

        if llm_debug_payload:
            response_payload["__llm_response"] = llm_debug_payload

        config_used = _as_mapping(llm_result.get("config_used"))
        provider_name = _coerce_str(config_used.get("provider_name")) if config_used else None
        llm_config_id = _coerce_int(config_used.get("id")) if config_used else None
        usage_payload = _as_mapping(llm_result.get("usage"))
        total_tokens = _coerce_int(usage_payload.get("total_tokens")) if usage_payload else 0
        request_payload = _as_mapping(llm_result.get("request_payload"))
        if request_payload:
            sanitized_request_payload = _sanitize_request_payload(dict(request_payload))
        else:
            logger.warning(
                "ai_request_log_missing_request_payload",
                user_qiao_id=user_qiao_id,
                instance_id=instance_context.get("instance_id"),
            )
            sanitized_request_payload = {"error": "request_payload_not_available"}
        response_time_value = _coerce_float(llm_result.get("response_time"))
        response_time_ms = int(response_time_value * 1000) if response_time_value is not None else 0
        success_flag = bool(llm_result.get("success"))

        request_log = AIRequestLog(
            instance_id=instance_context["instance_id"],
            user_id=user_id,  # FIXED: use user_id (int) not user_qiao_id (str)
            user_qiao_id=user_qiao_id,
            style_id=instance_context["style"]["id"],
            personality_id=instance_context["personality"]["id"],
            request_type="production",
            provider_name=provider_name,
            model_name=_coerce_str(llm_result.get("model")),
            llm_config_id=llm_config_id,
            response_id=llm_result.get("response_id"),
            cache_hit=bool(llm_result.get("cache_hit")),
            buffer_id=buffer_id,
            request=sanitized_request_payload,
            response=response_payload,
            status=1 if success_flag else 2,
            token_count=total_tokens,
            response_time=response_time_ms,
        )

        db.add(request_log)
        await db.flush()

        logger.debug(
            "ai_request_log_saved",
            instance_id=instance_context["instance_id"],
            user_id=user_id,
        )
        return int(request_log.id)

    except Exception as exc:
        logger.error(
            "ai_request_log_save_failed", error=str(exc), user_qiao_id=user_qiao_id, exc_info=True
        )
        # Don't raise - logging failure shouldn't break the conversation
        return None


def _coerce_response_payload(ai_response: object) -> dict[str, object]:
    """Normalize AI response payloads for persistence."""
    if isinstance(ai_response, Mapping):
        return dict(ai_response)
    return {"content": ai_response}


def _sanitize_request_payload(value: object) -> object:
    """Redact sensitive keys in request payloads before persistence."""
    if isinstance(value, Mapping):
        sanitized: dict[object, object] = {}
        for key, item in value.items():
            key_str = str(key).lower()
            if key_str in SENSITIVE_REQUEST_KEYS:
                sanitized[key] = "[redacted]"
            else:
                sanitized[key] = _sanitize_request_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_request_payload(item) for item in value]
    return value


def _as_mapping(value: object | None) -> Mapping[str, object] | None:
    """Safely treat objects as mapping payloads."""
    if isinstance(value, Mapping):
        return value
    return None


def _coerce_str(value: object | None) -> str | None:
    """Convert scalar values to strings."""
    if isinstance(value, str):
        return value
    return None


def _coerce_int(value: object | None) -> int | None:
    """Convert JSON-compatible numbers to integers."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _coerce_float(value: object | None) -> float | None:
    """Convert JSON-compatible numbers to floats."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
