"""
AI conversation service - conversation flow management.

This module handles the complete conversation processing flow,
coordinating all AI service components with clear error handling.
"""

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_sessionmaker
from app.enums import CHAT_INFO_TEMPLATES, AIMessageBufferState, ChatInfoType, ContactType
from app.exceptions import AIConversationError, AIInstanceInactiveError, AIInstanceNotFoundError
from app.exceptions.llm import JSONSchemaNotSupportedError
from app.models.ai.instance import AIInstance, AIMessageBuffer
from app.models.contact import Contact
from app.models.llm import LLMConfig, LLMProvider
from app.services.ai.context_archiving import archive_old_contexts
from app.services.ai.conversation_prompt import build_conversation_context, build_system_prompt
from app.services.ai.memory import process_memory_operations
from app.services.ai.orchestrators.llm_response_handler import process_llm_response
from app.services.ai.queries import get_instance_context, get_instance_relationship_scores
from app.services.ai.queries.transactions import save_ai_request_log
from app.services.ai.queries.updates import (
    mark_conversation_item_as_excluded,
    update_instance_status,
)
from app.services.ai.relationship_scoring import (
    calculate_new_scores,
    determine_relationship_type,
    get_relationship_scores,
    update_instance_current_relationship,
    update_relationship_positions,
)
from app.services.ai.response_schema import build_response_schema
from app.services.ai.utils.min_contract import (
    L0ContractResult,
    prune_l1_fields,
    validate_l0_contract,
)
from app.services.ai.utils.normalization import normalize_memory_operations, normalize_score_payload
from app.services.llm import invoke_llm
from app.services.llm.client import select_config_for_ai
from app.services.llm.config import get_instance_llm_config
from app.services.llm.streaming_policy import extract_stream_override, resolve_streaming_decision
from app.services.message.outbound.helpers import send_chat_info
from app.services.message.processing.buffer import finalize_buffer_if_locked
from app.services.message.processing.runtime import is_active_turn
from app.services.message.processing.sender import clear_conversation_pending_messages
from app.services.message.security.validation import message_validation_service
from app.services.system_config import get_config, get_config_int
from app.type_defs import InstanceContext, JSONDict, JSONValue, LLMSessionContext, PreemptionChecker
from app.utils.logging import get_logger

logger = get_logger(__name__)

_MIN_CONTRACT_RETRY_ENABLED_KEY = "ai_llm_min_contract_retry_enabled"
_MIN_CONTRACT_RETRY_MAX_ATTEMPTS_KEY = "ai_llm_min_contract_retry_max_attempts"
_MIN_CONTRACT_RETRY_BACKOFF_MS_KEY = "ai_llm_min_contract_retry_backoff_ms"


@dataclass(slots=True)
class ContextResolutionResult:
    context: InstanceContext | None
    contact: Contact | None
    instance_obj: AIInstance | None
    rejected_result: JSONDict | None = None


@dataclass(slots=True)
class AttemptExecutionResult:
    status: str
    llm_result: JSONDict | None = None
    ai_response: JSONDict | None = None
    llm_request_id: int | None = None
    raw_refresh_ids: object | None = None
    last_error: str | None = None


async def _load_min_contract_retry_config(db: AsyncSession) -> tuple[bool, int, int]:
    enabled_raw = await get_config(db, key=_MIN_CONTRACT_RETRY_ENABLED_KEY, required=True)
    if not isinstance(enabled_raw, bool):
        raise TypeError(f"{_MIN_CONTRACT_RETRY_ENABLED_KEY} must be boolean")

    max_attempts = await get_config_int(db, key=_MIN_CONTRACT_RETRY_MAX_ATTEMPTS_KEY, required=True)
    backoff_ms = await get_config_int(db, key=_MIN_CONTRACT_RETRY_BACKOFF_MS_KEY, required=True)

    if max_attempts < 1:
        raise ValueError(f"{_MIN_CONTRACT_RETRY_MAX_ATTEMPTS_KEY} must be >= 1")
    if backoff_ms < 0:
        raise ValueError(f"{_MIN_CONTRACT_RETRY_BACKOFF_MS_KEY} must be >= 0")

    if not enabled_raw:
        return False, 1, 0

    return True, max_attempts, backoff_ms


# Exception classes moved to exceptions/business.py for consistency


def _action_reason_from_chat_info_type(chat_info_type: ChatInfoType) -> str:
    mapping: dict[ChatInfoType, str] = {
        ChatInfoType.MESSAGE_BLOCKED: "MESSAGE_BLOCKED",
        ChatInfoType.NOT_FRIEND: "NOT_FRIEND",
        ChatInfoType.CONTACT_ADDED: "CONTACT_ADDED",
    }
    return mapping[chat_info_type]


async def _reject_as_business_result(
    db: AsyncSession,
    *,
    user_qiao_id: str,
    instance_qiao_id: str,
    template_key: ChatInfoType,
    error_code: str,
    reason: str,
    locked_buffer_id: int | None,
    conversation_id: str | None,
    task_turn_version: int | None,
) -> JSONDict:
    if locked_buffer_id is not None and task_turn_version is not None:
        if not await is_active_turn(
            db=db,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            task_turn_version=task_turn_version,
        ):
            return {
                "success": False,
                "error": "Conversation preempted by newer active turn",
                "preempted": True,
                "buffer_id": locked_buffer_id,
            }

    content = CHAT_INFO_TEMPLATES.get(template_key)
    if not content:
        raise AIConversationError(
            conversation_step="permission_validation",
            reason="chat_info_template_missing",
            message=f"Missing CHAT_INFO template for type={int(template_key)}",
        )

    action: JSONDict | None = None
    if locked_buffer_id is not None:
        result = await db.execute(
            select(AIMessageBuffer.last_msg_id_client).where(AIMessageBuffer.id == locked_buffer_id)
        )
        target_msg_id = result.scalar_one_or_none()
        if isinstance(target_msg_id, str) and target_msg_id:
            action = {
                "type": "mark_message_failed",
                "target_msg_id": target_msg_id,
                "reason": _action_reason_from_chat_info_type(template_key),
            }

    chat_info_sent = False
    if conversation_id:
        await send_chat_info(
            db=db,
            to_qiao_id=user_qiao_id,
            conversation_id=conversation_id,
            content=content,
            action=action,
        )
        chat_info_sent = True
    else:
        logger.warning(
            "chat_info_not_sent_conversation_missing",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            chat_info_type=int(template_key),
        )

    if locked_buffer_id is not None:
        await finalize_buffer_if_locked(
            db,
            locked_buffer_id,
            target_state=AIMessageBufferState.COMPLETE,
        )

    await db.commit()

    return {
        "success": True,
        "rejected": True,
        "buffer_id": locked_buffer_id,
        "error_code": error_code,
        "reason": reason,
        "chat_info_type": int(template_key),
        "chat_info_sent": chat_info_sent,
    }


def _build_preempted_result(locked_buffer_id: int | None) -> JSONDict:
    return {
        "success": False,
        "error": "Conversation preempted by newer active turn",
        "preempted": True,
        "buffer_id": locked_buffer_id,
    }


async def _resolve_context_for_processing(
    db: AsyncSession,
    *,
    persist: bool,
    user_qiao_id: str,
    instance_qiao_id: str,
    locked_buffer_id: int | None,
    task_turn_version: int | None,
) -> ContextResolutionResult:
    contact: Contact | None = None
    instance_obj: AIInstance | None = None

    if persist:
        contact_stmt = select(Contact).where(
            Contact.user_qiao_id == user_qiao_id,
            Contact.contact_qiao_id == instance_qiao_id,
            Contact.contact_type == ContactType.AI.value,
        )
        contact_result = await db.execute(contact_stmt)
        contact = contact_result.scalar_one_or_none()

        if not contact:
            logger.warning(
                "contact_not_found_for_validation",
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
            )
            rejected_result = await _reject_as_business_result(
                db,
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                template_key=ChatInfoType.NOT_FRIEND,
                error_code="contact_not_found",
                reason="Contact relationship not found between user and instance",
                locked_buffer_id=locked_buffer_id,
                conversation_id=None,
                task_turn_version=task_turn_version,
            )
            return ContextResolutionResult(
                context=None,
                contact=None,
                instance_obj=None,
                rejected_result=rejected_result,
            )

        instance_obj = await db.get(AIInstance, contact.contact_id)
        if not instance_obj:
            logger.error(
                "instance_not_found_for_contact",
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                contact_id=contact.contact_id,
            )
            raise AIConversationError(
                conversation_step="instance_lookup",
                reason="instance_not_found",
                message=f"Instance not found: {instance_qiao_id}",
            )

        context = await get_instance_context(db, instance_id=instance_obj.id)
    else:
        context = await get_instance_context(
            db,
            instance_qiao_id=instance_qiao_id,
            user_qiao_id=user_qiao_id,
        )

    if not context:
        raise AIConversationError(
            conversation_step="instance_lookup",
            reason="instance_not_found",
            message=f"Instance not found: {instance_qiao_id}",
        )

    return ContextResolutionResult(
        context=context,
        contact=contact,
        instance_obj=instance_obj,
        rejected_result=None,
    )


async def _validate_message_permission_or_reject(
    db: AsyncSession,
    *,
    persist: bool,
    user_qiao_id: str,
    instance_qiao_id: str,
    locked_buffer_id: int | None,
    task_turn_version: int | None,
    contact: Contact | None,
    instance_obj: AIInstance | None,
) -> JSONDict | None:
    if not (persist and instance_obj and contact):
        logger.debug(
            "skipping_contact_validation_in_test_mode",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
        )
        return None

    validation_result = await message_validation_service.validate_message_permission(
        db=db, from_qiao_id=user_qiao_id, instance=instance_obj, contact=contact
    )
    if validation_result.allowed:
        return None

    logger.warning(
        "message_permission_denied",
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        reason=validation_result.reason,
        error_code=validation_result.error_code,
    )
    template_key = validation_result.chat_info_type or ChatInfoType.MESSAGE_BLOCKED
    return await _reject_as_business_result(
        db,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        template_key=template_key,
        error_code=validation_result.error_code or "permission_denied",
        reason=validation_result.reason or "Message permission denied",
        locked_buffer_id=locked_buffer_id,
        conversation_id=contact.conversation_id,
        task_turn_version=task_turn_version,
    )


def _should_append_user_message(
    *,
    user_text: str,
    persist: bool,
    user_message_item_id: int | None,
    conversation_history: list[JSONDict],
) -> bool:
    if not user_text:
        return False
    if not (persist and user_message_item_id is not None):
        return True
    if not conversation_history:
        return True

    last_entry = conversation_history[-1]
    if last_entry.get("role") != "user":
        return True

    last_text = last_entry.get("text_content")
    if not isinstance(last_text, str):
        return True

    last_text_clean = last_text.strip()
    if last_text_clean.startswith("["):
        closing_index = last_text_clean.find("]")
        if closing_index != -1:
            last_text_clean = last_text_clean[closing_index + 1 :].lstrip()

    return last_text_clean != user_text.strip()


def _build_messages_for_llm(
    *,
    system_prompt: str,
    conversation_history: list[JSONDict],
    user_text: str,
    persist: bool,
    user_message_item_id: int | None,
    timezone_name: str | None,
) -> list[JSONDict]:
    messages: list[JSONDict] = []
    if system_prompt:
        messages.append(
            {
                "role": "system",
                "message_type": "text",
                "text_content": system_prompt,
            }
        )
    messages.extend(conversation_history)

    if _should_append_user_message(
        user_text=user_text,
        persist=persist,
        user_message_item_id=user_message_item_id,
        conversation_history=conversation_history,
    ):
        prefix = _format_now_prefix(timezone_name)
        formatted_user_text = f"[{prefix}] {user_text}" if prefix else user_text
        messages.append(
            {
                "role": "user",
                "message_type": "text",
                "text_content": formatted_user_text,
            }
        )
    return messages


async def _prepare_preemption_checker(
    *,
    db: AsyncSession,
    config: LLMConfig,
    provider: LLMProvider,
    stream_override: bool | None,
    locked_buffer_id: int | None,
    user_qiao_id: str,
    instance_qiao_id: str,
    task_turn_version: int | None,
) -> tuple[PreemptionChecker | None, JSONDict | None]:
    if locked_buffer_id is None or task_turn_version is None:
        return None, None

    async def check_preemption() -> bool:
        return not await is_active_turn(
            db=db,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            task_turn_version=task_turn_version,
        )

    preview_decision = resolve_streaming_decision(
        config=config,
        provider=provider,
        enable_override=stream_override,
        has_preemption_checker=True,
    )
    if not preview_decision.should_stream:
        logger.debug(
            "streaming_disabled_for_context",
            buffer_id=locked_buffer_id,
            reason=preview_decision.reason,
        )

    if await check_preemption():
        logger.info(
            "conversation_preempted_before_llm",
            buffer_id=locked_buffer_id,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            task_turn_version=task_turn_version,
        )
        return None, _build_preempted_result(locked_buffer_id)

    return check_preemption, None


def _build_style_dimension_names(context: InstanceContext) -> list[str]:
    dimension_names: list[str] = []
    for dim in context.get("dimensions", []):
        dim_name = dim.get("name") if isinstance(dim, dict) else None
        if not isinstance(dim_name, str) or not dim_name:
            raise AIConversationError(
                conversation_step="llm_request",
                reason="invalid_style_dimensions",
                message="Invalid style dimension name in instance context",
            )
        dimension_names.append(dim_name)
    return dimension_names


def _build_attempt_diag(
    *,
    attempt_index: int,
    attempt_total: int,
    failure_code: str | None,
    failure_detail: str | None,
    l0_ok: bool,
    l1_score_kept: bool,
    l1_memory_kept: bool,
    preempted: bool,
) -> JSONDict:
    return {
        "attempt_index": attempt_index,
        "attempt_total": attempt_total,
        "failure_code": failure_code,
        "failure_detail": failure_detail,
        "l0_ok": l0_ok,
        "l1_score_kept": l1_score_kept,
        "l1_memory_kept": l1_memory_kept,
        "preempted": preempted,
    }


async def _save_attempt_log(
    *,
    db: AsyncSession,
    context: InstanceContext,
    user_qiao_id: str,
    llm_result: JSONDict,
    buffer_id: int | None,
    attempt_diag: JSONDict,
    ai_response: JSONDict | None = None,
) -> int | None:
    response_payload: JSONDict = dict(ai_response) if ai_response is not None else {}
    response_payload["__min_contract"] = attempt_diag
    return await save_ai_request_log(
        db=db,
        instance_context=context,
        user_qiao_id=user_qiao_id,
        ai_response=response_payload,
        llm_result=llm_result,
        buffer_id=buffer_id,
    )


def _normalize_l0_fields_into_response(
    *,
    response_payload: JSONDict,
    l0_result: L0ContractResult,
) -> JSONDict:
    normalized_response = dict(response_payload)
    for key in (
        "attack_detected",
        "should_block",
        "should_reply",
        "outgoing_messages",
        "followup_messages",
    ):
        normalized_response.pop(key, None)
    if l0_result.attack_detected is not None:
        normalized_response["attack_detected"] = l0_result.attack_detected
    if l0_result.should_block is not None:
        normalized_response["should_block"] = l0_result.should_block
    if l0_result.should_reply is not None:
        normalized_response["should_reply"] = l0_result.should_reply
    if l0_result.outgoing_messages is not None:
        normalized_response["outgoing_messages"] = list(l0_result.outgoing_messages)
    if l0_result.followup_messages is not None:
        normalized_response["followup_messages"] = list(l0_result.followup_messages)
    return normalized_response


async def _execute_llm_attempts(
    *,
    db: AsyncSession,
    context: InstanceContext,
    user_qiao_id: str,
    instance_qiao_id: str,
    messages: list[JSONDict],
    json_schema: JSONDict,
    effective_config_name: str,
    instance_request_params: JSONDict,
    preemption_checker: PreemptionChecker | None,
    locked_buffer_id: int | None,
    attempt_total: int,
    backoff_ms: int,
) -> AttemptExecutionResult:
    style_dimension_names = _build_style_dimension_names(context)
    successful_llm_result: JSONDict | None = None
    successful_ai_response: JSONDict | None = None
    successful_attempt_log_id: int | None = None
    successful_raw_refresh_ids: object | None = None
    last_error: str | None = None

    for attempt_index in range(1, attempt_total + 1):
        if preemption_checker and await preemption_checker():
            return AttemptExecutionResult(status="preempted")

        llm_result = await invoke_llm(
            db=db,
            messages=messages,
            json_schema=json_schema,
            name=effective_config_name,
            instance_request_params=instance_request_params,
            preemption_checker=preemption_checker,
            session_context=LLMSessionContext(
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
            ),
        )

        if bool(llm_result.get("preempted")):
            await _save_attempt_log(
                db=db,
                context=context,
                user_qiao_id=user_qiao_id,
                llm_result=llm_result,
                buffer_id=locked_buffer_id,
                attempt_diag=_build_attempt_diag(
                    attempt_index=attempt_index,
                    attempt_total=attempt_total,
                    failure_code="PREEMPTED",
                    failure_detail="stream_preempted",
                    l0_ok=False,
                    l1_score_kept=False,
                    l1_memory_kept=False,
                    preempted=True,
                ),
            )
            await db.commit()
            return AttemptExecutionResult(status="preempted")

        if not bool(llm_result.get("success")):
            last_error = str(llm_result.get("error") or "llm_request_failed")
            await _save_attempt_log(
                db=db,
                context=context,
                user_qiao_id=user_qiao_id,
                llm_result=llm_result,
                buffer_id=locked_buffer_id,
                attempt_diag=_build_attempt_diag(
                    attempt_index=attempt_index,
                    attempt_total=attempt_total,
                    failure_code="LLM_REQUEST_FAILED",
                    failure_detail=last_error,
                    l0_ok=False,
                    l1_score_kept=False,
                    l1_memory_kept=False,
                    preempted=False,
                ),
            )
            await db.commit()
        else:
            response_payload = llm_result.get("response")
            if not isinstance(response_payload, dict):
                last_error = "response is not a JSON object"
                failed_llm_result = dict(llm_result)
                failed_llm_result["success"] = False
                failed_llm_result["error"] = last_error
                await _save_attempt_log(
                    db=db,
                    context=context,
                    user_qiao_id=user_qiao_id,
                    llm_result=failed_llm_result,
                    buffer_id=locked_buffer_id,
                    attempt_diag=_build_attempt_diag(
                        attempt_index=attempt_index,
                        attempt_total=attempt_total,
                        failure_code="JSON_PARSE_FAILED",
                        failure_detail=last_error,
                        l0_ok=False,
                        l1_score_kept=False,
                        l1_memory_kept=False,
                        preempted=False,
                    ),
                )
                await db.commit()
            else:
                l0_result = validate_l0_contract(response_payload, json_schema)
                if not l0_result.ok:
                    last_error = l0_result.failure_detail or "l0_validation_failed"
                    failed_llm_result = dict(llm_result)
                    failed_llm_result["success"] = False
                    failed_llm_result["error"] = last_error
                    await _save_attempt_log(
                        db=db,
                        context=context,
                        user_qiao_id=user_qiao_id,
                        llm_result=failed_llm_result,
                        buffer_id=locked_buffer_id,
                        attempt_diag=_build_attempt_diag(
                            attempt_index=attempt_index,
                            attempt_total=attempt_total,
                            failure_code=l0_result.failure_code or "L0_FAILED",
                            failure_detail=last_error,
                            l0_ok=False,
                            l1_score_kept=False,
                            l1_memory_kept=False,
                            preempted=False,
                        ),
                    )
                    await db.commit()
                else:
                    raw_refresh_ids = None
                    raw_memory_operations = response_payload.get("memory_operations")
                    if isinstance(raw_memory_operations, dict):
                        raw_refresh_ids = raw_memory_operations.get("refresh_ids")
                    normalized_response = _normalize_l0_fields_into_response(
                        response_payload=response_payload,
                        l0_result=l0_result,
                    )
                    l1_result = prune_l1_fields(
                        ai_response=normalized_response,
                        style_dimension_names=style_dimension_names,
                        personality_schema=context["personality"].get("json_schema"),
                    )
                    normalized_response = l1_result.pruned_response
                    successful_attempt_log_id = await _save_attempt_log(
                        db=db,
                        context=context,
                        user_qiao_id=user_qiao_id,
                        llm_result=llm_result,
                        buffer_id=locked_buffer_id,
                        attempt_diag=_build_attempt_diag(
                            attempt_index=attempt_index,
                            attempt_total=attempt_total,
                            failure_code=None,
                            failure_detail=None,
                            l0_ok=True,
                            l1_score_kept=l1_result.score_kept,
                            l1_memory_kept=l1_result.memory_kept,
                            preempted=False,
                        ),
                        ai_response=normalized_response,
                    )
                    await db.commit()
                    successful_llm_result = llm_result
                    successful_ai_response = normalized_response
                    successful_raw_refresh_ids = raw_refresh_ids
                    break

        if attempt_index < attempt_total:
            if preemption_checker and await preemption_checker():
                return AttemptExecutionResult(status="preempted")
            if backoff_ms > 0:
                await asyncio.sleep(backoff_ms / 1000)
            if preemption_checker and await preemption_checker():
                return AttemptExecutionResult(status="preempted")

    if successful_llm_result is None or successful_ai_response is None:
        logger.warning(
            "min_contract_attempts_exhausted",
            buffer_id=locked_buffer_id,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            attempts=attempt_total,
            last_error=last_error,
        )
        return AttemptExecutionResult(status="silent_failed", last_error=last_error)

    return AttemptExecutionResult(
        status="success",
        llm_result=successful_llm_result,
        ai_response=successful_ai_response,
        llm_request_id=successful_attempt_log_id,
        raw_refresh_ids=successful_raw_refresh_ids,
    )


async def _handle_retry_config_error(
    *,
    db: AsyncSession,
    context: InstanceContext,
    user_qiao_id: str,
    instance_qiao_id: str,
    locked_buffer_id: int | None,
    error: Exception,
    effective_config_name: str,
    messages: list[JSONDict],
    json_schema: JSONDict,
    config_id: int,
    config_name: str,
    provider_name: str,
    model_name: str | None,
) -> None:
    logger.error(
        "min_contract_retry_config_invalid",
        error=str(error),
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
    )
    messages_payload: list[JSONValue] = [dict(message) for message in messages]
    await _save_attempt_log(
        db=db,
        context=context,
        user_qiao_id=user_qiao_id,
        llm_result={
            "success": False,
            "error": str(error),
            "usage": None,
            "model": None,
            "response_time": 0,
            "request_payload": {
                "config_name": effective_config_name,
                "messages": messages_payload,
                "json_schema": json_schema,
            },
            "config_used": {
                "id": config_id,
                "name": config_name,
                "provider_name": provider_name,
                "model": model_name,
            },
        },
        buffer_id=locked_buffer_id,
        attempt_diag=_build_attempt_diag(
            attempt_index=1,
            attempt_total=1,
            failure_code="CONFIG_ERROR",
            failure_detail=str(error),
            l0_ok=False,
            l1_score_kept=False,
            l1_memory_kept=False,
            preempted=False,
        ),
    )
    if locked_buffer_id is not None:
        await clear_conversation_pending_messages(db, user_qiao_id, instance_qiao_id)
        await finalize_buffer_if_locked(
            db,
            locked_buffer_id,
            target_state=AIMessageBufferState.COMPLETE,
        )
    await db.commit()


async def _resolve_terminal_attempt_result(
    *,
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
    locked_buffer_id: int | None,
    attempt_result: AttemptExecutionResult,
) -> JSONDict | None:
    if attempt_result.status == "preempted":
        return _build_preempted_result(locked_buffer_id)

    if attempt_result.status != "silent_failed":
        return None

    if locked_buffer_id is not None:
        await clear_conversation_pending_messages(db, user_qiao_id, instance_qiao_id)
        await finalize_buffer_if_locked(
            db,
            locked_buffer_id,
            target_state=AIMessageBufferState.COMPLETE,
        )
        await db.commit()
    return {
        "success": True,
        "buffer_id": locked_buffer_id,
        "silent_failed": True,
    }


async def process_conversation(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
    message_content: str,
    message_type: str = "text",
    config_name: str | None = None,
    request_overrides: JSONDict | None = None,
    locked_buffer_id: int | None = None,
    user_message_item_id: int | None = None,
    message_blocks: list[JSONDict] | None = None,
    persist: bool = True,
    task_turn_version: int | None = None,
) -> JSONDict:
    """Wrapper to run conversation flow with consistent error handling."""
    try:
        return await _process_conversation_impl(
            db=db,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            message_content=message_content,
            message_type=message_type,
            config_name=config_name,
            request_overrides=request_overrides,
            locked_buffer_id=locked_buffer_id,
            user_message_item_id=user_message_item_id,
            message_blocks=message_blocks,
            persist=persist,
            task_turn_version=task_turn_version,
        )
    except (AIInstanceNotFoundError, AIInstanceInactiveError) as exc:
        logger.error(
            "conversation_processing_instance_error",
            error=str(exc),
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
        )
        raise AIConversationError(
            conversation_step="instance_validation",
            reason="instance_error",
            message=f"Instance error: {exc!s}",
        ) from exc
    except AIConversationError:
        raise
    except Exception as exc:
        logger.error(
            "conversation_processing_unexpected_error",
            error=str(exc),
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
        )
        raise AIConversationError(
            conversation_step="processing",
            reason="unexpected_error",
            message=f"Unexpected error in conversation processing: {exc!s}",
        ) from exc


async def _process_conversation_impl(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
    message_content: str,
    message_type: str = "text",
    config_name: str | None = None,
    request_overrides: JSONDict | None = None,
    locked_buffer_id: int | None = None,
    user_message_item_id: int | None = None,
    message_blocks: list[JSONDict] | None = None,
    persist: bool = True,
    task_turn_version: int | None = None,
) -> JSONDict:
    """
    Process AI conversation following the complete 11-step flow.

    This is the main entry point that orchestrates the complete conversation
    processing flow as defined in the prototype design.

    Steps:
    1. Merge short-time messages (buffer) - simplified for now
    2. Persist user window into ai_conversation_items
    3. Find corresponding ai_instance
    4. Find corresponding relationship_score
    5. Find relationship based on ai_style
    6. Apply relationship prompt and placeholders to personality template
    7. Get context and merge with system prompt
    8. Request LLM
    9. Validate with JSON Schema (done in LLM call)
    10. Update ai_instance_dimension and other related content
    11. Reply message

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        instance_qiao_id: Instance's qiao_id
        message_content: User's message content (text fallback)
        message_type: Message type (text, image, etc.)
        locked_buffer_id: Locked buffer ID (if triggered by buffer)
        user_message_item_id: Conversation history row id tied to locked buffer
        message_blocks: Structured content blocks (Responses API format)

    Returns:
        Dictionary containing conversation processing result
    Raises:
        ConversationProcessingError: If processing fails
    """
    logger.info(
        "conversation_processing_started",
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        message_type=message_type,
    )

    if persist and locked_buffer_id is not None and task_turn_version is None:
        raise AIConversationError(
            conversation_step="preemption_guard",
            reason="missing_task_turn_version",
            message="task_turn_version is required when processing a locked buffer",
        )

    context_resolution = await _resolve_context_for_processing(
        db,
        persist=persist,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        locked_buffer_id=locked_buffer_id,
        task_turn_version=task_turn_version,
    )
    early_rejection_result = context_resolution.rejected_result
    context = context_resolution.context
    if early_rejection_result is None:
        if context is None:
            raise AIConversationError(
                conversation_step="instance_lookup",
                reason="instance_context_missing",
                message="Instance context resolution failed unexpectedly",
            )
        permission_rejection = await _validate_message_permission_or_reject(
            db,
            persist=persist,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            locked_buffer_id=locked_buffer_id,
            task_turn_version=task_turn_version,
            contact=context_resolution.contact,
            instance_obj=context_resolution.instance_obj,
        )
        early_rejection_result = permission_rejection
    if early_rejection_result is not None:
        return early_rejection_result
    if context is None:
        raise AIConversationError(
            conversation_step="instance_lookup",
            reason="instance_context_missing",
            message="Instance context resolution failed unexpectedly",
        )

    relationship_scores = await get_relationship_scores(db, context["instance_id"])
    relationship_type = await determine_relationship_type(db, context, relationship_scores)
    system_prompt = await build_system_prompt(db, context, relationship_type, user_qiao_id)
    conversation_history = await build_conversation_context(
        db,
        instance_qiao_id,
        user_qiao_id,
        max_context_length=None,
        instance_timezone=context.get("timezone"),
    )

    user_text = message_content if message_content else _blocks_to_text(message_blocks or [])
    messages = _build_messages_for_llm(
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        user_text=user_text,
        persist=persist,
        user_message_item_id=user_message_item_id,
        timezone_name=context.get("timezone"),
    )

    # Get JSON schema for response validation
    json_schema = build_response_schema(context)

    # Select config (override or instance). Block only if JSON Schema is explicitly disabled.
    if config_name:
        config, provider = await select_config_for_ai(db, config_name)
        config_lookup_mode = "test_override"
    else:
        instance_id = context["instance_id"]
        config, provider = await get_instance_llm_config(db, instance_id)
        config_lookup_mode = "instance"

    if provider.name != "mock" and config.json_schema_mode == "disabled":
        raise JSONSchemaNotSupportedError(config_name=config.name)

    logger.info(
        "ai_conversation_config_validated",
        config_name=config.name,
        provider=provider.name,
        json_schema_mode=config.json_schema_mode,
        lookup_mode=config_lookup_mode,
    )

    # Extract instance-specific request parameters
    instance_request_params = dict(context.get("request_params") or {})
    # Apply test-time overrides (e.g., mock provider)
    if request_overrides:
        with suppress(Exception):
            instance_request_params = {**instance_request_params, **request_overrides}
    if instance_request_params:
        logger.debug(
            "using_instance_request_params",
            instance_qiao_id=instance_qiao_id,
            params=instance_request_params,
        )

    stream_override = extract_stream_override(instance_request_params)
    if stream_override is not None:
        instance_request_params["enable_streaming"] = stream_override

    preemption_checker, preempted_result = await _prepare_preemption_checker(
        db=db,
        config=config,
        provider=provider,
        stream_override=stream_override,
        locked_buffer_id=locked_buffer_id,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        task_turn_version=task_turn_version,
    )
    if preempted_result is not None:
        return preempted_result

    # No hardcoded parameters - use config priority: instance_request_params > config
    effective_config_name = config_name or config.name
    try:
        retry_enabled, max_attempts, backoff_ms = await _load_min_contract_retry_config(db)
    except Exception as exc:
        await _handle_retry_config_error(
            db=db,
            context=context,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            locked_buffer_id=locked_buffer_id,
            error=exc,
            effective_config_name=effective_config_name,
            messages=messages,
            json_schema=json_schema,
            config_id=config.id,
            config_name=config.name,
            provider_name=provider.name,
            model_name=config.model_name or provider.default_model,
        )
        raise AIConversationError(
            conversation_step="system_config",
            reason="min_contract_retry_config_invalid",
            message=str(exc),
        ) from exc

    attempt_total = max_attempts if retry_enabled else 1
    attempt_result = await _execute_llm_attempts(
        db=db,
        context=context,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        messages=messages,
        json_schema=json_schema,
        effective_config_name=effective_config_name,
        instance_request_params=instance_request_params,
        preemption_checker=preemption_checker,
        locked_buffer_id=locked_buffer_id,
        attempt_total=attempt_total,
        backoff_ms=backoff_ms,
    )

    terminal_attempt_result = await _resolve_terminal_attempt_result(
        db=db,
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        locked_buffer_id=locked_buffer_id,
        attempt_result=attempt_result,
    )
    if terminal_attempt_result is not None:
        return terminal_attempt_result

    if attempt_result.llm_result is None or attempt_result.ai_response is None:
        raise AIConversationError(
            conversation_step="llm_request",
            reason="missing_attempt_result",
            message="Attempt result missing successful response payload",
        )
    llm_result = attempt_result.llm_result
    ai_response = attempt_result.ai_response

    # Step 10 & 11: Save all conversation results in single atomic transaction
    assistant_item_id: int | None = None
    if persist:
        session_factory = get_sessionmaker()
        response_result = await process_llm_response(
            db=db,
            session_factory=session_factory,
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            instance_context=context,
            ai_response=ai_response,
            llm_result={
                "success": True,
                "model": llm_result.get("model"),
                "usage": llm_result.get("usage", {}),
                "config_used": llm_result.get("config_used"),
                "request_payload": llm_result.get("request_payload"),
                "response_time": llm_result.get("response_time", 0),
                "response_id": llm_result.get("response_id"),
                "cache_hit": llm_result.get("cache_hit"),
                "cache_strategy": llm_result.get("cache_strategy"),
                "raw_response": llm_result.get("raw_response"),
                "raw_content": llm_result.get("raw_content"),
                "tool_calls": llm_result.get("tool_calls"),
                "reasoning_content": llm_result.get("reasoning_content"),
                "finish_reason": llm_result.get("finish_reason"),
                "streaming": llm_result.get("streaming"),
            },
            llm_request_id=attempt_result.llm_request_id,
            raw_refresh_ids=attempt_result.raw_refresh_ids,
            locked_buffer_id=locked_buffer_id,
            user_message_item_id=user_message_item_id,
            task_turn_version=task_turn_version,
        )
        if not bool(response_result.get("success", True)):
            return response_result
    else:
        # Non-persist mode: only update scores/memory without sending messages
        await process_ai_response_updates(
            db,
            user_qiao_id,
            instance_qiao_id,
            context,
            ai_response,
            locked_buffer_id,
            user_message_item_id,
            persist=False,
        )

    # Archive old contexts if needed (per user-instance conversation)
    await archive_old_contexts(db, user_qiao_id, instance_qiao_id)

    logger.info(
        "conversation_processing_completed",
        user_qiao_id=user_qiao_id,
        instance_qiao_id=instance_qiao_id,
        buffer_id=locked_buffer_id,
    )

    return {
        "success": True,
        "buffer_id": locked_buffer_id,
        "assistant_item_id": assistant_item_id,
        "response": ai_response,
        "usage": llm_result.get("usage", {}),
        "model": llm_result.get("model"),
        "config_used": llm_result.get("config_used"),
        "request_payload": llm_result.get("request_payload"),
    }


async def process_ai_response_updates(
    db: AsyncSession,
    user_qiao_id: str,
    instance_qiao_id: str,
    context: InstanceContext,
    ai_response: JSONDict,
    buffer_id: int | None,  # Locked buffer id
    user_message_item_id: int | None,
    *,
    persist: bool = True,
) -> None:
    """
    Process AI response and update related data.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        instance_qiao_id: Instance's qiao_id
        context: Instance context data
        ai_response: AI response dictionary
        buffer_id: Buffer ID (used for logging only)
        user_message_item_id: Conversation item identifier linked to buffer
    """
    try:
        # No state transition here; buffer controls OPEN -> LOCKED -> COMPLETE

        # Handle attack detection
        if (
            persist
            and ai_response.get("attack_detected", False)
            and user_message_item_id is not None
        ):
            await handle_attack_detection(db, user_qiao_id, instance_qiao_id, user_message_item_id)

        # Update relationship scores
        score_payload = normalize_score_payload(ai_response.get("score"))
        if score_payload:
            new_scores = await calculate_new_scores(db, context, score_payload)

            # Update relationship positions
            instance_id = context["instance_id"]
            if persist and instance_id and new_scores:
                await update_relationship_positions(db, instance_id, new_scores)

                # Re-evaluate and persist current relationship after score update
                latest_scores = await get_instance_relationship_scores(db, instance_id)
                if persist and latest_scores:
                    rel = await determine_relationship_type(db, context, latest_scores)
                    if rel and rel.get("relationship"):
                        relationship = rel["relationship"]
                        display_name = getattr(
                            relationship, "display_name", getattr(relationship, "name", "")
                        )
                        await update_instance_current_relationship(
                            db, instance_id, relationship.id, display_name
                        )

        # Process memory operations
        memory_operations = normalize_memory_operations(ai_response.get("memory_operations"))
        has_operations = any(
            memory_operations[key] for key in ("remove", "update", "refresh_ids", "add")
        )
        if persist and ai_response.get("should_update_memory", False) and has_operations:
            await process_memory_operations(
                db,
                context,
                memory_operations,
                source_message_id=user_message_item_id,
            )

        # Handle blocking
        if persist and ai_response.get("should_block", False):
            await handle_instance_blocking(db, context["instance_id"], instance_qiao_id)

        # Finalization to COMPLETE is handled by buffer after this function returns

        logger.debug(
            "ai_response_updates_completed",
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            buffer_id=buffer_id,
        )

    except Exception as e:
        logger.error(
            "ai_response_updates_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            buffer_id=buffer_id,
        )
        # Non-fatal error: log but continue


async def handle_attack_detection(
    db: AsyncSession, user_qiao_id: str, instance_qiao_id: str, conversation_item_id: int
) -> None:
    """
    Handle detected prompt injection attack.

    Args:
        db: Database session
        user_qiao_id: User's qiao_id
        instance_qiao_id: Instance's qiao_id
        conversation_item_id: Conversation row tied to the suspicious message
    """
    try:
        # Mark conversation item as excluded from context using data layer
        success = await mark_conversation_item_as_excluded(db, conversation_item_id)

        if success:
            # TODO: Log security incident to user_violation_logs
            logger.warning(
                "attack_detected_and_handled",
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                conversation_item_id=conversation_item_id,
            )
        else:
            logger.error(
                "failed_to_mark_attack",
                user_qiao_id=user_qiao_id,
                instance_qiao_id=instance_qiao_id,
                conversation_item_id=conversation_item_id,
            )

    except Exception as e:
        logger.error(
            "attack_handling_failed",
            error=str(e),
            user_qiao_id=user_qiao_id,
            instance_qiao_id=instance_qiao_id,
            conversation_item_id=conversation_item_id,
        )


async def handle_instance_blocking(
    db: AsyncSession, instance_id: int, instance_qiao_id: str
) -> None:
    """
    Handle instance blocking (delete friend).

    Args:
        db: Database session
        instance_id: Instance ID
        instance_qiao_id: Instance's qiao_id
    """
    try:
        success = await update_instance_status(db, instance_id, 3)  # blocked

        if success:
            logger.warning("instance_blocked", instance_qiao_id=instance_qiao_id)
        else:
            logger.error("failed_to_block_instance", instance_qiao_id=instance_qiao_id)

    except Exception as e:
        logger.error("instance_blocking_failed", error=str(e), instance_qiao_id=instance_qiao_id)


def _blocks_to_text(blocks: list[JSONDict]) -> str:
    """Flatten provider-style blocks into a single text string."""

    fragments: list[str] = []
    for block in blocks:
        text_value = block.get("text")
        if isinstance(text_value, str) and text_value:
            fragments.append(text_value)
    return "\n".join(fragments)


def _format_now_prefix(timezone_name: str | None) -> str | None:
    """
    Format current time with humanized format.

    For current messages, always returns "今天HH:MM" format.
    Falls back to Asia/Shanghai timezone.
    """
    try:
        tz = timezone_name or "Asia/Shanghai"
        try:
            tzinfo = ZoneInfo(tz)
        except Exception:
            tzinfo = ZoneInfo("Asia/Shanghai")
        now = datetime.now(tzinfo)
        # For current messages, always use "今天HH:MM" format
        return f"今天{now.strftime('%H:%M')}"
    except Exception:
        return None
