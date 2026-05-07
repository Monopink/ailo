from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.enums import AlertDomain, AlertEventType, AlertSeverityLevel
from app.services.alerting import events


class _SessionContext:
    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


@pytest.mark.asyncio
async def test_emit_alert_injects_required_details_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(events, "get_sessionmaker", lambda: lambda: _SessionContext(session))
    insert_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(events.alert_events, "insert_unique_with_entities", insert_mock)

    inserted = await events.emit_alert(
        event_type=AlertEventType.AI_CONVERSATION_SYSTEM_FAILURE,
        domain=AlertDomain.AI_CONVERSATION,
        severity_level=AlertSeverityLevel.ERROR,
        dedupe_fields={"instance_qiao_id": "ai_001"},
        details={"error_message": "boom"},
    )

    assert inserted is True
    assert session.commit.await_count == 1
    assert insert_mock.await_count == 1
    call_kwargs = insert_mock.await_args.kwargs
    details = call_kwargs["details"]
    assert details["schema_version"] == 1
    assert details["error_code"] == "AI_CONVERSATION_SYSTEM_FAILURE"
    assert "date_bucket_utc=" in call_kwargs["dedupe_key"]


@pytest.mark.asyncio
async def test_emit_alert_returns_false_when_insert_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(events, "get_sessionmaker", lambda: lambda: _SessionContext(session))
    monkeypatch.setattr(
        events.alert_events,
        "insert_unique_with_entities",
        AsyncMock(side_effect=RuntimeError("db_down")),
    )

    inserted = await events.emit_alert(
        event_type=AlertEventType.MESSAGE_DISPATCH_TASK_FAILED,
        domain=AlertDomain.MESSAGE_DISPATCH,
        severity_level=AlertSeverityLevel.ERROR,
        dedupe_fields={"outbox_id": 1},
        details={"schema_version": 1},
    )

    assert inserted is False
