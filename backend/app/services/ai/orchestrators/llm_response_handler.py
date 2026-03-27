"""
LLM response processing orchestrator.

Coordinates persistence side effects for LLM responses and launches
asynchronous message sending tasks.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.enums import AIMessageBufferState
from app.models.ai import AIInstance
from app.services.ai.memory import process_memory_operations
from app.services.ai.memory.alerting import maybe_write_refresh_miss_alert
from app.services.ai.queries.instance_queries import get_instance_relationship_config
from app.services.ai.queries.relationship_queries import get_instance_relationship_scores
from app.services.ai.queries.security_updates import create_attack_detected_violation_log
from app.services.ai.queries.updates import (
    mark_conversation_item_as_excluded,
    set_instance_current_relationship,
    update_instance_relationship_scores,
    update_instance_status,
)
from app.services.ai.relationship_scoring import determine_relationship_type
from app.services.ai.utils.normalization import normalize_memory_operations, normalize_score_payload
from app.services.message.processing.buffer import finalize_buffer_if_locked
from app.services.message.processing.runtime import is_active_turn
from app.services.message.processing.sender import (
    SendExecutionResult,
    clear_conversation_pending_messages,
    send_ai_messages_with_typing,
)
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
    llm_request_id: int | None,
    locked_buffer_id: int | None,
    user_message_item_id: int | None,
    task_turn_version: int | None,
    raw_refresh_ids: object | None = None,
) -> JSONDict:
    """Persist side effects from one LLM response and emit outgoing messages."""
    _ = llm_result

    outgoing_messages: list[str] = _coerce_string_list(ai_response.get("outgoing_messages"))
    followup_messages: list[str] = _coerce_string_list(ai_response.get("followup_messages"))
    should_reply = bool(ai_response.get("should_reply", True))

    score_updates = normalize_score_payload(ai_response.get("score"))
    raw_refresh_ids = _resolve_raw_refresh_ids(
        ai_response=ai_response,
        raw_refresh_ids=raw_refresh_ids,
    )
    memory_ops_payload = normalize_memory_operations(ai_response.get("memory_operations"))
    has_memory_ops = any(
        memory_ops_payload[key] for key in ("remove", "update", "refresh_ids", "add")
    )
    should_apply_memory = bool(ai_response.get("should_update_memory")) and has_memory_ops

    if task_turn_version is None:
        raise ValueError("task_turn_version is required for response handling")

    if locked_buffer_id is not None and not await is_active_turn(
        db=db,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        task_turn_version=task_turn_version,
    ):
        logger.info(
            "conversation_response_preempted_before_side_effects",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            task_turn_version=task_turn_version,
        )
        return {
            "success": False,
            "error": "Conversation preempted by newer active turn",
            "preempted": True,
            "buffer_id": locked_buffer_id,
        }

    try:
        if ai_response.get("attack_detected") and user_message_item_id:
            excluded_ok = await mark_conversation_item_as_excluded(db, user_message_item_id)
            if not excluded_ok:
                logger.error(
                    "attack_detected_exclude_mark_failed",
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    conversation_item_id=user_message_item_id,
                )

            violation_ok = await create_attack_detected_violation_log(
                db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                instance_id=int(instance_context["instance_id"]),
                conversation_item_id=int(user_message_item_id),
            )
            _ = violation_ok

        if ai_response.get("should_block"):
            blocked_ok = await update_instance_status(db, instance_context["instance_id"], status=3)
            if not blocked_ok:
                raise RuntimeError("failed_to_apply_should_block")
        await db.commit()

        logger.info(
            "conversation_safety_side_effects_saved",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            buffer_id=locked_buffer_id,
            task_turn_version=task_turn_version,
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

    if should_reply and (outgoing_messages or followup_messages):
        typing_speed_seconds_per_word = await _resolve_typing_speed_seconds_per_word(
            db, instance_context["instance_id"]
        )
        followup_delay_seconds = await _resolve_followup_delay_seconds(
            db, instance_context["instance_id"]
        )
    else:
        outgoing_messages = []
        followup_messages = []
        typing_speed_seconds_per_word = DEFAULT_TYPING_SPEED_SECONDS_PER_WORD
        followup_delay_seconds = 0.0

    # should_reply=false: skip outgoing sending, while still allowing side effects
    # after an explicit preemption guard.
    if not should_reply:
        if locked_buffer_id is not None:
            if not await is_active_turn(
                db=db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                task_turn_version=task_turn_version,
            ):
                logger.info(
                    "conversation_reply_disabled_preempted",
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    task_turn_version=task_turn_version,
                )
                return {
                    "success": False,
                    "error": "Conversation preempted by newer active turn",
                    "preempted": True,
                    "buffer_id": locked_buffer_id,
                }
            await clear_conversation_pending_messages(db, user_qiao_id, instance_qiao_id)
            await finalize_buffer_if_locked(
                db,
                locked_buffer_id,
                target_state=AIMessageBufferState.COMPLETE,
            )
            await db.commit()

        if should_apply_memory or score_updates:
            side_effect_task = asyncio.create_task(
                _apply_side_effects_without_send(
                    session_factory=session_factory,
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    llm_request_id=llm_request_id,
                    task_turn_version=task_turn_version,
                    instance_context=instance_context,
                    score_updates=score_updates,
                    should_apply_memory=should_apply_memory,
                    memory_ops_payload=memory_ops_payload,
                    raw_refresh_ids=raw_refresh_ids,
                    user_message_item_id=user_message_item_id,
                )
            )
            side_effect_task.add_done_callback(_log_send_task_failure)

        return {"success": True, "buffer_id": locked_buffer_id}

    send_task = asyncio.create_task(
        _send_and_apply_post_send_effects(
            session_factory=session_factory,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            buffer_id=locked_buffer_id,
            outgoing_messages=outgoing_messages,
            followup_messages=followup_messages,
            typing_speed_seconds_per_word=typing_speed_seconds_per_word,
            followup_delay_seconds=followup_delay_seconds,
            llm_request_id=llm_request_id,
            task_turn_version=task_turn_version,
            instance_context=instance_context,
            score_updates=score_updates,
            should_apply_memory=should_apply_memory,
            memory_ops_payload=memory_ops_payload,
            raw_refresh_ids=raw_refresh_ids,
            user_message_item_id=user_message_item_id,
        )
    )
    send_task.add_done_callback(_log_send_task_failure)

    return {
        "success": True,
        "buffer_id": locked_buffer_id,
    }


async def _apply_side_effects_without_send(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    user_qiao_id: str,
    instance_qiao_id: str,
    llm_request_id: int | None,
    task_turn_version: int,
    instance_context: InstanceContext,
    score_updates: dict[str, int],
    should_apply_memory: bool,
    memory_ops_payload: JSONDict,
    raw_refresh_ids: object,
    user_message_item_id: int | None,
) -> None:
    if not should_apply_memory and not score_updates:
        return

    if should_apply_memory:
        await _apply_memory_side_effect(
            session_factory=session_factory,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            llm_request_id=llm_request_id,
            task_turn_version=task_turn_version,
            instance_context=instance_context,
            memory_ops_payload=memory_ops_payload,
            raw_refresh_ids=raw_refresh_ids,
            user_message_item_id=user_message_item_id,
        )

    if score_updates:
        await _apply_score_side_effect(
            session_factory=session_factory,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            task_turn_version=task_turn_version,
            instance_context=instance_context,
            score_updates=score_updates,
        )


async def _send_and_apply_post_send_effects(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    user_qiao_id: str,
    instance_qiao_id: str,
    buffer_id: int | None,
    outgoing_messages: list[str],
    followup_messages: list[str],
    typing_speed_seconds_per_word: float,
    followup_delay_seconds: float,
    llm_request_id: int | None,
    task_turn_version: int,
    instance_context: InstanceContext,
    score_updates: dict[str, int],
    should_apply_memory: bool,
    memory_ops_payload: JSONDict,
    raw_refresh_ids: object,
    user_message_item_id: int | None,
) -> None:
    send_result: SendExecutionResult = await send_ai_messages_with_typing(
        session_factory=session_factory,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        buffer_id=buffer_id,
        outgoing_messages=outgoing_messages,
        followup_messages=followup_messages,
        typing_speed_seconds_per_word=typing_speed_seconds_per_word,
        followup_delay_seconds=followup_delay_seconds,
        llm_request_id=llm_request_id,
        task_turn_version=task_turn_version,
    )

    if not send_result.first_message_sent:
        logger.info(
            "conversation_side_effects_skipped_without_first_send",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            task_turn_version=task_turn_version,
        )
        return

    if not should_apply_memory and not score_updates:
        return

    if should_apply_memory:
        await _apply_memory_side_effect(
            session_factory=session_factory,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            llm_request_id=llm_request_id,
            task_turn_version=task_turn_version,
            instance_context=instance_context,
            memory_ops_payload=memory_ops_payload,
            raw_refresh_ids=raw_refresh_ids,
            user_message_item_id=user_message_item_id,
        )

    if score_updates:
        await _apply_score_side_effect(
            session_factory=session_factory,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            task_turn_version=task_turn_version,
            instance_context=instance_context,
            score_updates=score_updates,
        )


async def _apply_memory_side_effect(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    user_qiao_id: str,
    instance_qiao_id: str,
    llm_request_id: int | None,
    task_turn_version: int,
    instance_context: InstanceContext,
    memory_ops_payload: JSONDict,
    raw_refresh_ids: object,
    user_message_item_id: int | None,
) -> None:
    async with session_factory() as db:
        try:
            if not await is_active_turn(
                db=db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                task_turn_version=task_turn_version,
            ):
                logger.info(
                    "conversation_memory_side_effect_preempted",
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    task_turn_version=task_turn_version,
                )
                return
            memory_exec = await process_memory_operations(
                db,
                instance_context,
                memory_ops_payload,
                source_message_id=user_message_item_id,
            )
            await db.commit()
            logger.info(
                "conversation_memory_side_effect_applied_after_send",
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                task_turn_version=task_turn_version,
                refresh_total=memory_exec.refresh.total,
                refresh_miss=memory_exec.refresh.miss,
                refresh_miss_ratio_bp=memory_exec.refresh.miss_ratio_bp,
            )

            try:
                await maybe_write_refresh_miss_alert(
                    session_factory=session_factory,
                    context=instance_context,
                    llm_request_id=llm_request_id,
                    task_turn_version=task_turn_version,
                    refresh_exec=memory_exec.refresh,
                    raw_refresh_ids=raw_refresh_ids,
                )
            except Exception as exc:
                logger.error(
                    "conversation_memory_refresh_alert_failed",
                    error=str(exc),
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    task_turn_version=task_turn_version,
                    llm_request_id=llm_request_id,
                    exc_info=True,
                )
        except Exception as exc:
            await db.rollback()
            logger.error(
                "conversation_memory_side_effect_failed_after_send",
                error=str(exc),
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                task_turn_version=task_turn_version,
                exc_info=True,
            )


async def _apply_score_side_effect(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    user_qiao_id: str,
    instance_qiao_id: str,
    task_turn_version: int,
    instance_context: InstanceContext,
    score_updates: dict[str, int],
) -> None:
    async with session_factory() as db:
        try:
            if not await is_active_turn(
                db=db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                task_turn_version=task_turn_version,
            ):
                logger.info(
                    "conversation_score_side_effect_preempted",
                    user_qiao_id=user_qiao_id,
                    instance_qiao_id=instance_qiao_id,
                    task_turn_version=task_turn_version,
                )
                return
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

            await db.commit()
            logger.info(
                "conversation_score_side_effect_applied_after_send",
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                task_turn_version=task_turn_version,
            )
        except Exception as exc:
            await db.rollback()
            logger.error(
                "conversation_score_side_effect_failed_after_send",
                error=str(exc),
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                task_turn_version=task_turn_version,
                exc_info=True,
            )


async def _resolve_typing_speed_seconds_per_word(db: AsyncSession, instance_id: int) -> float:
    """Derive seconds per word based on the instance's configured WPM."""

    stmt = select(AIInstance.typing_speed_wpm).where(AIInstance.id == instance_id)
    result = await db.execute(stmt)
    value = result.scalar_one_or_none()

    wpm = DEFAULT_TYPING_SPEED_WPM if value is None else int(value)
    if wpm <= 0:
        logger.warning(
            "invalid_typing_speed_wpm",
            instance_id=instance_id,
            configured_value=wpm,
        )
        wpm = DEFAULT_TYPING_SPEED_WPM

    return 60.0 / float(wpm)


async def _resolve_followup_delay_seconds(db: AsyncSession, instance_id: int) -> float:
    """Resolve follow-up delay from relationship configuration."""

    config = await get_instance_relationship_config(db, instance_id=instance_id)
    if not config:
        raise ValueError("Missing followup_delay_ms configuration")

    followup_delay_ms_value = config.get("followup_delay_ms")
    followup_delay_ms = _coerce_delay_value(followup_delay_ms_value)
    if followup_delay_ms is None:
        raise ValueError("Missing followup_delay_ms configuration")

    return followup_delay_ms / 1000.0


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


def _resolve_raw_refresh_ids(*, ai_response: JSONDict, raw_refresh_ids: object | None) -> object:
    """Prefer explicitly propagated raw refresh ids and fall back to response payload."""
    if raw_refresh_ids is not None:
        return raw_refresh_ids
    memory_operations = ai_response.get("memory_operations")
    if isinstance(memory_operations, dict):
        return memory_operations.get("refresh_ids")
    return None


def _log_send_task_failure(task: asyncio.Task[None]) -> None:
    """Log any exceptions raised by the background send task."""
    try:
        task.result()
    except Exception as exc:  # pragma: no cover - log only
        logger.error("send_ai_messages_task_failed", error=str(exc))
