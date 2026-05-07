from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest

from app.enums import AlertEventType
from app.exceptions import AIConversationError, MissingConfigurationError
from app.services.ai.orchestrators import conversation_flow
from app.type_defs import InstanceContext


@pytest.mark.asyncio
async def test_process_conversation_impl_handles_context_policy_config_errors_as_silent_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Context policy configuration errors should end the turn silently."""
    resolved_context = cast(
        InstanceContext,
        {
            "instance_id": 1,
            "instance_qiao_id": "ai_1",
            "user_qiao_id": "user_1",
            "timezone": "UTC",
        },
    )
    monkeypatch.setattr(
        conversation_flow,
        "_resolve_context_for_processing",
        AsyncMock(
            return_value=conversation_flow.ContextResolutionResult(
                context=resolved_context,
                contact=None,
                instance_obj=None,
                rejected_result=None,
            )
        ),
    )
    monkeypatch.setattr(
        conversation_flow,
        "_validate_message_permission_or_reject",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        conversation_flow,
        "_load_ai_conversation_context_policy",
        AsyncMock(side_effect=MissingConfigurationError("ai_conversation_context_max_messages")),
    )
    handle_error_mock = AsyncMock()
    monkeypatch.setattr(
        conversation_flow,
        "_handle_ai_conversation_context_config_error",
        handle_error_mock,
    )

    result = await conversation_flow._process_conversation_impl(
        db=cast(object, object()),
        user_qiao_id="user_1",
        instance_qiao_id="ai_1",
        message_content="hello",
        persist=False,
    )

    assert result["success"] is True
    assert result["silent_failed"] is True
    handle_error_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_conversation_impl_does_not_swallow_non_config_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-config errors must not be mislabeled as silent config failures."""
    resolved_context = cast(
        InstanceContext,
        {
            "instance_id": 1,
            "instance_qiao_id": "ai_1",
            "user_qiao_id": "user_1",
            "timezone": "UTC",
        },
    )
    monkeypatch.setattr(
        conversation_flow,
        "_resolve_context_for_processing",
        AsyncMock(
            return_value=conversation_flow.ContextResolutionResult(
                context=resolved_context,
                contact=None,
                instance_obj=None,
                rejected_result=None,
            )
        ),
    )
    monkeypatch.setattr(
        conversation_flow,
        "_validate_message_permission_or_reject",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        conversation_flow,
        "_load_ai_conversation_context_policy",
        AsyncMock(side_effect=RuntimeError("db_unavailable")),
    )
    handle_error_mock = AsyncMock()
    monkeypatch.setattr(
        conversation_flow,
        "_handle_ai_conversation_context_config_error",
        handle_error_mock,
    )

    with pytest.raises(RuntimeError, match="db_unavailable"):
        await conversation_flow._process_conversation_impl(
            db=cast(object, object()),
            user_qiao_id="user_1",
            instance_qiao_id="ai_1",
            message_content="hello",
            persist=False,
        )

    handle_error_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_conversation_emits_system_failure_alert_for_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        conversation_flow,
        "_process_conversation_impl",
        AsyncMock(side_effect=RuntimeError("unexpected_boom")),
    )
    emit_alert_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(conversation_flow, "emit_alert", emit_alert_mock)

    with pytest.raises(AIConversationError, match="Unexpected error in conversation processing"):
        await conversation_flow.process_conversation(
            db=cast(object, object()),
            user_qiao_id="user_1",
            instance_qiao_id="ai_1",
            message_content="hello",
            locked_buffer_id=100,
            task_turn_version=7,
        )

    assert emit_alert_mock.await_count == 1
    call_kwargs = emit_alert_mock.await_args.kwargs
    assert call_kwargs["event_type"] == AlertEventType.AI_CONVERSATION_SYSTEM_FAILURE


@pytest.mark.asyncio
async def test_handle_context_config_error_keeps_main_flow_when_alert_emit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit_mock = AsyncMock()
    db = SimpleNamespace(commit=commit_mock)
    monkeypatch.setattr(conversation_flow, "_save_attempt_log", AsyncMock(return_value=1))
    monkeypatch.setattr(conversation_flow, "clear_conversation_pending_messages", AsyncMock())
    monkeypatch.setattr(conversation_flow, "finalize_buffer_if_locked", AsyncMock())
    monkeypatch.setattr(
        conversation_flow, "emit_alert", AsyncMock(side_effect=RuntimeError("boom"))
    )

    await conversation_flow._handle_ai_conversation_context_config_error(
        db=cast(object, db),
        context=cast(
            InstanceContext,
            {
                "instance_id": 1,
                "instance_qiao_id": "ai_1",
                "user_id": 2,
                "user_qiao_id": "user_1",
                "timezone": "UTC",
            },
        ),
        user_qiao_id="user_1",
        instance_qiao_id="ai_1",
        locked_buffer_id=123,
        error=MissingConfigurationError("ai_conversation_context_max_messages"),
        task_turn_version=9,
    )

    assert commit_mock.await_count == 1
