import sys
import types
from unittest.mock import AsyncMock

import pytest

if "chinese_calendar" not in sys.modules:
    chinese_calendar_stub = types.ModuleType("chinese_calendar")
    chinese_calendar_stub.get_holiday_detail = lambda _target_date: (False, None)
    sys.modules["chinese_calendar"] = chinese_calendar_stub

if "lunar_python" not in sys.modules:
    lunar_python_stub = types.ModuleType("lunar_python")

    class _SolarStub:
        @staticmethod
        def fromYmdHms(*_args, **_kwargs):  # noqa: N802
            raise RuntimeError("not used in this test")

        @staticmethod
        def fromYmd(*_args, **_kwargs):  # noqa: N802
            raise RuntimeError("not used in this test")

    lunar_python_stub.Solar = _SolarStub
    sys.modules["lunar_python"] = lunar_python_stub

from app.services.ai.orchestrators import llm_response_handler


class _DummyAsyncSession:
    async def commit(self) -> None:  # pragma: no cover - should not be called in this test
        return None

    async def rollback(self) -> None:  # pragma: no cover - should not be called in this test
        return None


@pytest.mark.asyncio
async def test_process_llm_response_returns_preempted_before_any_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    is_active_turn_mock = AsyncMock(return_value=False)
    attack_exclude_mock = AsyncMock()
    block_mock = AsyncMock()

    monkeypatch.setattr(llm_response_handler, "is_active_turn", is_active_turn_mock)
    monkeypatch.setattr(
        llm_response_handler, "mark_conversation_item_as_excluded", attack_exclude_mock
    )
    monkeypatch.setattr(llm_response_handler, "update_instance_status", block_mock)

    result = await llm_response_handler.process_llm_response(
        db=_DummyAsyncSession(),  # type: ignore[arg-type]
        session_factory=None,  # type: ignore[arg-type]
        user_qiao_id="u1",
        instance_qiao_id="ai1",
        instance_context={"instance_id": 1},  # type: ignore[arg-type]
        ai_response={"attack_detected": True, "should_block": True, "should_reply": True},
        llm_result={"success": True},
        llm_request_id=123,
        locked_buffer_id=999,
        user_message_item_id=101,
        task_turn_version=8,
    )

    assert result["success"] is False
    assert result["preempted"] is True
    assert result["buffer_id"] == 999
    attack_exclude_mock.assert_not_awaited()
    block_mock.assert_not_awaited()
