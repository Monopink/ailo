from typing import cast
from unittest.mock import AsyncMock

import pytest

from app.exceptions import MissingConfigurationError
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
