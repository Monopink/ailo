"""
LLM response processing orchestrator.

Coordinates persistence side effects for LLM responses and launches
asynchronous message sending tasks.
"""

import asyncio
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.ai import AIInstance
from app.services.ai.memory import process_memory_operations
from app.services.ai.queries.instance_queries import get_instance_relationship_config
from app.services.ai.queries.relationship_queries import get_instance_relationship_scores
from app.services.ai.queries.transactions import save_ai_request_log
from app.services.ai.queries.updates import (
    mark_conversation_item_as_excluded,
    set_instance_current_relationship,
    update_instance_relationship_scores,
    update_instance_status,
)
from app.services.ai.relationship_scoring import determine_relationship_type
from app.services.message.processing.buffer import finalize_buffer_if_locked
from app.services.message.processing.sender import send_ai_messages_with_typing
from app.type_defs import InstanceContext, JSONDict, JSONValue
from app.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TYPING_SPEED_WPM = 50
DEFAULT_TYPING_SPEED_SECONDS_PER_WORD = 60.0 / DEFAULT_TYPING_SPEED_WPM


async def process_llm_response(
    db: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    user_qiao_id: str,
    instance_qiao_id: str,
    instance_context: InstanceContext,
    ai_response: JSONDict,
    llm_result: JSONDict,
    locked_buffer_id: int | None,
    user_message_item_id: int | None,
) -> JSONDict:
    """Persist side effects from one LLM response and emit outgoing messages."""

    try:
        score_updates = _normalize_score_payload(ai_response.get("score"))

        if score_updates:
            await update_instance_relationship_scores(
                db, instance_context["instance_id"], score_updates
            )

            latest_scores = await get_instance_relationship_scores(
                db, instance_context["instance_id"]
            )
            if latest_scores:
                rel = await determine_relationship_type(db, instance_context, latest_scores)
                if rel and rel.get("relationship"):
                    relationship = rel["relationship"]
                    display_name = getattr(
                        relationship, "display_name", getattr(relationship, "name", "")
                    )
                    await set_instance_current_relationship(
                        db, instance_context["instance_id"], relationship.id, display_name
                    )

        memory_ops_payload = _normalize_memory_operations(ai_response.get("memory_operations"))
        has_memory_ops = any(
            memory_ops_payload[key] for key in ("remove", "update", "refresh", "add")
        )
        if ai_response.get("should_update_memory") and has_memory_ops:
            await process_memory_operations(
                db,
                instance_context,
                memory_ops_payload,
                source_message_id=user_message_item_id,
            )

        if ai_response.get("attack_detected") and user_message_item_id:
            await mark_conversation_item_as_excluded(db, user_message_item_id)

        if ai_response.get("should_block"):
            await update_instance_status(db, instance_qiao_id, status=3)

        await save_ai_request_log(
            db=db,
            instance_context=instance_context,
            user_qiao_id=user_qiao_id,
            ai_response=ai_response,
            llm_result=llm_result,
            buffer_id=locked_buffer_id,
        )

        if locked_buffer_id:
            await finalize_buffer_if_locked(db, locked_buffer_id)

        await db.commit()

        logger.info(
            "conversation_result_saved",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            buffer_id=locked_buffer_id,
        )

    except Exception as exc:  # pragma: no cover - orchestration level logging only
        await db.rollback()
        logger.error(
            "conversation_result_save_failed",
            error=str(exc),
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            exc_info=True,
        )
        raise

    outgoing_messages: list[str] = _coerce_string_list(ai_response.get("outgoing_messages"))
    followup_messages: list[str] = _coerce_string_list(ai_response.get("followup_messages"))
    should_reply = bool(ai_response.get("should_reply", True))

    if should_reply and (outgoing_messages or followup_messages):
        typing_speed_seconds_per_word = await _resolve_typing_speed_seconds_per_word(
            db, instance_qiao_id
        )
        followup_delay_seconds = await _resolve_followup_delay_seconds(db, instance_qiao_id)
    else:
        outgoing_messages = []
        followup_messages = []
        typing_speed_seconds_per_word = DEFAULT_TYPING_SPEED_SECONDS_PER_WORD
        followup_delay_seconds = 0.0

    send_task = asyncio.create_task(
        send_ai_messages_with_typing(
            session_factory=session_factory,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            buffer_id=locked_buffer_id,
            outgoing_messages=outgoing_messages,
            followup_messages=followup_messages,
            typing_speed_seconds_per_word=typing_speed_seconds_per_word,
            followup_delay_seconds=followup_delay_seconds,
        )
    )
    send_task.add_done_callback(_log_send_task_failure)

    return {
        "success": True,
        "buffer_id": locked_buffer_id,
    }


async def _resolve_typing_speed_seconds_per_word(db: AsyncSession, instance_qiao_id: str) -> float:
    """Derive seconds per word based on the instance's configured WPM."""

    stmt = select(AIInstance.typing_speed_wpm).where(AIInstance.qiao_id == instance_qiao_id)
    result = await db.execute(stmt)
    value = result.scalar_one_or_none()

    wpm = DEFAULT_TYPING_SPEED_WPM if value is None else int(value)
    if wpm <= 0:
        logger.warning(
            "invalid_typing_speed_wpm",
            instance_qiao_id=instance_qiao_id,
            configured_value=wpm,
        )
        wpm = DEFAULT_TYPING_SPEED_WPM

    return 60.0 / float(wpm)


async def _resolve_followup_delay_seconds(db: AsyncSession, instance_qiao_id: str) -> float:
    """Resolve follow-up delay from relationship configuration."""

    config = await get_instance_relationship_config(db, instance_qiao_id)
    if not config:
        raise ValueError("Missing followup_delay_ms configuration")

    followup_delay_ms_value = config.get("followup_delay_ms")
    followup_delay_ms = _coerce_delay_value(followup_delay_ms_value)
    if followup_delay_ms is None:
        raise ValueError("Missing followup_delay_ms configuration")

    return followup_delay_ms / 1000.0


def _normalize_memory_operations(value: JSONValue | None) -> JSONDict:
    """Normalize LLM-provided memory operations into canonical structure."""
    normalized: JSONDict = {"remove": [], "update": [], "refresh": [], "add": []}
    if not isinstance(value, dict):
        return normalized

    remove_items = value.get("remove")
    if isinstance(remove_items, list):
        normalized["remove"] = [item for item in remove_items if isinstance(item, str) and item]

    update_items = value.get("update")
    if isinstance(update_items, list):
        updates: list[JSONDict] = []
        for item in update_items:
            if not isinstance(item, dict):
                continue
            old_content = item.get("old_content")
            new_content = item.get("new_content")
            if not isinstance(old_content, str) or not isinstance(new_content, str):
                continue
            entry: JSONDict = {"old_content": old_content, "new_content": new_content}
            new_importance = item.get("new_importance")
            if isinstance(new_importance, int | float):
                entry["new_importance"] = int(new_importance)
            updates.append(entry)
        normalized["update"] = cast(list[JSONValue], updates)

    refresh_items = value.get("refresh")
    if isinstance(refresh_items, list):
        normalized["refresh"] = [item for item in refresh_items if isinstance(item, str) and item]

    add_items = value.get("add")
    if isinstance(add_items, list):
        additions: list[JSONDict] = []
        for item in add_items:
            if not isinstance(item, dict):
                continue
            memory_type = item.get("memory_type")
            content = item.get("content")
            importance = item.get("importance")
            if memory_type not in {"core", "recent"}:
                continue
            if not isinstance(content, str) or not content:
                continue
            if not isinstance(importance, int | float):
                continue
            additions.append(
                {
                    "memory_type": memory_type,
                    "content": content,
                    "importance": int(importance),
                }
            )
        normalized["add"] = cast(list[JSONValue], additions)

    return normalized


def _normalize_score_payload(score_value: JSONValue | None) -> dict[str, int]:
    """Convert JSON payload into normalized integer mapping."""
    if not isinstance(score_value, dict):
        return {}

    normalized: dict[str, int] = {}
    for key, value in score_value.items():
        coerced_value = _coerce_score_value(value)
        if coerced_value is not None:
            normalized[key] = coerced_value
    return normalized


def _coerce_score_value(value: JSONValue) -> int | None:
    """Convert JSON scalar score values into ints."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    return None


def _coerce_string_list(value: JSONValue | None) -> list[str]:
    """Ensure a JSON value is returned as a string list."""
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, str):
        return [value]
    return []


def _coerce_delay_value(value: JSONValue | None) -> float | None:
    """Convert JSON-style delay values to floats."""
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


def _log_send_task_failure(task: asyncio.Task[JSONDict | None]) -> None:
    """Log any exceptions raised by the background send task."""
    try:
        task.result()
    except Exception as exc:  # pragma: no cover - log only
        logger.error("send_ai_messages_task_failed", error=str(exc))
