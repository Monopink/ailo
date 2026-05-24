from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.enums import (
    AITemplateStatus,
    ContactRequestFailureCode,
    ContactRequestRetryFailureCode,
    ContactRequestRetryMode,
    ContactRequestRetryRuleCode,
    ContactRequestStatus,
)
from app.services.contact import incomplete_admin_service as panel_service
from app.services.contact import incomplete_retry_service as retry_service


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value


class _RowsResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _RowsResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _OverviewSession:
    def __init__(self) -> None:
        self.statements: list[Any] = []
        self._values = [128, 42, 17, 64, 9]
        self._index = 0

    async def execute(self, statement: Any) -> _ScalarResult:
        self.statements.append(statement)
        value = self._values[self._index]
        self._index += 1
        return _ScalarResult(value)


class _ListSession:
    def __init__(self, rows: list[Any], total: int) -> None:
        self._rows = rows
        self._total = total
        self._index = 0

    async def execute(self, _statement: Any) -> Any:
        if self._index == 0:
            self._index += 1
            return _ScalarResult(self._total)
        self._index += 1
        return _RowsResult(self._rows)


class _ActionSession:
    def __init__(self, row: Any | None) -> None:
        self.row = row
        self.added: list[Any] = []
        self.committed = False

    async def get(self, _model: Any, _request_id: int, with_for_update: bool = False) -> Any:
        assert with_for_update is True
        return self.row

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed = True

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_overview_contract_and_blocked_filter_query_shape() -> None:
    session = _OverviewSession()

    payload = await panel_service.get_incomplete_contact_request_overview(session)  # type: ignore[arg-type]

    assert set(payload.keys()) == {
        "incomplete_total",
        "last24h_success_requests",
        "last24h_failed_requests",
        "last24h_failed_attempts",
        "last24h_blocked_attempts",
    }

    blocked_stmt = session.statements[4]
    blocked_sql = str(blocked_stmt).upper()
    assert "RESULT_STATUS" in blocked_sql
    assert "RESULT_FAILURE_CODE" in blocked_sql
    assert "NOT IN" in blocked_sql

    params = blocked_stmt.compile().params
    flattened_values: list[str] = []
    for raw in params.values():
        if isinstance(raw, (list, tuple, set)):
            flattened_values.extend(str(item) for item in raw)
        else:
            flattened_values.append(str(raw))

    assert ContactRequestRetryFailureCode.AI_CONTACT_LIMIT_REACHED.value in flattened_values
    assert ContactRequestRetryFailureCode.RETRY_REJECTED.value in flattened_values


@pytest.mark.asyncio
async def test_list_contract_returns_only_required_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = SimpleNamespace(
        id=273338979288485888,
        status=int(ContactRequestStatus.PENDING),
        from_qiao_id="qiao_user_001",
        to_qiao_id="qiao_ai_target_001",
        from_id=273338979288485111,
        to_id=None,
        from_type=1,
        to_type=2,
        failure_code=ContactRequestFailureCode.ALL_TEMPLATES_ALREADY_USED.value,
        retry_count=2,
        created_at=datetime(2026, 5, 22, 4, 15, 1, tzinfo=UTC),
        expires_at=datetime(2026, 5, 29, 4, 15, 1, tzinfo=UTC),
        updated_at=datetime(2026, 5, 22, 5, 1, 11, tzinfo=UTC),
        last_retry_at=datetime(2026, 5, 22, 4, 58, 11, tzinfo=UTC),
        failure_detail={"ai_type_id": 3},
    )
    session = _ListSession(rows=[row], total=1)

    async def _fake_ai_type_map(_db: Any, *, ai_type_ids: set[str]) -> dict[str, str]:
        assert ai_type_ids == {"3"}
        return {"3": "校园学姐"}

    monkeypatch.setattr(panel_service, "_load_ai_type_name_map", _fake_ai_type_map)

    payload = await panel_service.list_incomplete_contact_requests(
        session,  # type: ignore[arg-type]
        limit=20,
        offset=0,
    )

    item = payload["items"][0]
    assert set(item.keys()) == {
        "request_id",
        "status",
        "from_qiao_id",
        "to_qiao_id",
        "from_id",
        "to_id",
        "from_type",
        "to_type",
        "failure_code",
        "failure_reason_label",
        "ai_type_id",
        "ai_type_display_name",
        "retry_count",
        "is_retryable",
        "created_at",
        "expires_at",
        "is_expired",
        "updated_at",
        "last_retry_at",
    }


@pytest.mark.asyncio
async def test_manual_precheck_blocks_used_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact_request = SimpleNamespace(
        id=123,
        status=ContactRequestStatus.PENDING,
        from_id=1001,
        to_qiao_id="ai_target_001",
        failure_code=ContactRequestFailureCode.MANUAL_PROVISION_REQUIRED.value,
        failure_detail={"ai_type_id": 3},
    )
    template = SimpleNamespace(
        id=12,
        display_name="Friendly Default",
        type_id=3,
        status=int(AITemplateStatus.ACTIVE),
        is_reusable=1,
        priority=1,
        style_id=7,
        personality_id=9,
        timezone="Asia/Shanghai",
        updated_at=datetime(2026, 5, 22, 6, 1, 11, tzinfo=UTC),
    )

    async def _fake_load_request(_db: Any, *, request_id: int, for_update: bool) -> Any:
        assert request_id == 123
        assert for_update is False
        return contact_request

    async def _fake_load_ai_type_name(_db: Any, *, ai_type_id: int | None) -> str | None:
        if ai_type_id is None:
            return None
        return f"Type-{ai_type_id}"

    async def _fake_availability(
        _db: Any, *, user_id: int, ai_type_id: int | None
    ) -> tuple[int, int]:
        assert user_id == 1001
        assert ai_type_id == 3
        return 3, 2

    async def _fake_load_template(_db: Any, *, template_id: int, for_update: bool) -> Any:
        assert template_id == 12
        assert for_update is False
        return template

    async def _always_used(_db: Any, *, user_id: int, template_id: int) -> bool:
        assert user_id == 1001
        assert template_id == 12
        return True

    monkeypatch.setattr(retry_service, "_load_retryable_pending_request", _fake_load_request)
    monkeypatch.setattr(retry_service, "_load_ai_type_display_name", _fake_load_ai_type_name)
    monkeypatch.setattr(retry_service, "_load_template_availability_counts", _fake_availability)
    monkeypatch.setattr(retry_service, "_load_template_for_retry", _fake_load_template)
    monkeypatch.setattr(retry_service, "_is_template_used_by_user", _always_used)

    payload = await retry_service.precheck_incomplete_contact_request_retry(
        db=SimpleNamespace(),
        request_id=123,
        mode=ContactRequestRetryMode.MANUAL,
        selected_ai_type_id=3,
        selected_template_id=12,
    )

    assert payload["summary"]["can_execute"] is False
    assert (
        payload["blocking_errors"][0]["code"]
        == ContactRequestRetryRuleCode.TEMPLATE_ALREADY_USED_BY_USER.value
    )


@pytest.mark.asyncio
async def test_manual_precheck_warnings_without_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact_request = SimpleNamespace(
        id=124,
        status=ContactRequestStatus.PENDING,
        from_id=1001,
        to_qiao_id="ai_target_001",
        failure_code=ContactRequestFailureCode.MANUAL_PROVISION_REQUIRED.value,
        failure_detail={"ai_type_id": 3},
    )
    template = SimpleNamespace(
        id=13,
        display_name="Inactive Template",
        type_id=4,
        status=int(AITemplateStatus.INACTIVE),
        is_reusable=1,
        priority=1,
        style_id=7,
        personality_id=9,
        timezone="Asia/Shanghai",
        updated_at=datetime(2026, 5, 22, 6, 1, 11, tzinfo=UTC),
    )

    async def _fake_load_request(_db: Any, *, request_id: int, for_update: bool) -> Any:
        assert request_id == 124
        assert for_update is False
        return contact_request

    async def _fake_load_ai_type_name(_db: Any, *, ai_type_id: int | None) -> str | None:
        if ai_type_id is None:
            return None
        return f"Type-{ai_type_id}"

    async def _fake_availability(
        _db: Any, *, user_id: int, ai_type_id: int | None
    ) -> tuple[int, int]:
        assert user_id == 1001
        assert ai_type_id == 3
        return 3, 2

    async def _fake_load_template(_db: Any, *, template_id: int, for_update: bool) -> Any:
        assert template_id == 13
        assert for_update is False
        return template

    async def _never_used(_db: Any, *, user_id: int, template_id: int) -> bool:
        assert user_id == 1001
        assert template_id == 13
        return False

    monkeypatch.setattr(retry_service, "_load_retryable_pending_request", _fake_load_request)
    monkeypatch.setattr(retry_service, "_load_ai_type_display_name", _fake_load_ai_type_name)
    monkeypatch.setattr(retry_service, "_load_template_availability_counts", _fake_availability)
    monkeypatch.setattr(retry_service, "_load_template_for_retry", _fake_load_template)
    monkeypatch.setattr(retry_service, "_is_template_used_by_user", _never_used)

    payload = await retry_service.precheck_incomplete_contact_request_retry(
        db=SimpleNamespace(),
        request_id=124,
        mode=ContactRequestRetryMode.MANUAL,
        selected_ai_type_id=3,
        selected_template_id=13,
    )

    warning_codes = {item["code"] for item in payload["warnings"]}
    assert ContactRequestRetryRuleCode.TEMPLATE_TYPE_MISMATCH.value in warning_codes
    assert ContactRequestRetryRuleCode.TEMPLATE_STATUS_NON_ACTIVE.value in warning_codes
    assert payload["blocking_errors"] == []
    assert payload["summary"]["can_execute"] is True


@pytest.mark.asyncio
async def test_admin_ignore_incomplete_request_changes_status() -> None:
    row = SimpleNamespace(
        id=99,
        status=ContactRequestStatus.PENDING,
        to_qiao_id="qiao_ai_target_001",
        failure_code=ContactRequestFailureCode.ALL_TEMPLATES_ALREADY_USED.value,
        failure_detail={"ai_type_id": 3},
    )
    session = _ActionSession(row)

    payload = await panel_service.admin_ignore_incomplete_contact_request(
        session,  # type: ignore[arg-type]
        request_id=99,
        operator_admin_user_id=1,
        operator_username="admin",
        operator_role=1,
    )

    assert payload["request_id"] == "99"
    assert payload["status"] == int(ContactRequestStatus.IGNORED)
    assert int(row.status) == int(ContactRequestStatus.IGNORED)
    assert row.failure_code is None
    assert row.failure_detail is None
    assert session.committed is True


@pytest.mark.asyncio
async def test_admin_reopen_ignored_request_to_pending_keeps_expires_at_unchanged() -> None:
    now = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)
    original_expires_at = now - timedelta(days=2)
    row = SimpleNamespace(
        id=100,
        status=ContactRequestStatus.IGNORED,
        to_qiao_id="qiao_ai_target_002",
        to_type=2,
        expires_at=original_expires_at,
        failure_code=None,
        failure_detail=None,
    )
    session = _ActionSession(row)

    class _PersonaResult:
        def one_or_none(self) -> Any:
            return SimpleNamespace(type_id=3, qiao_id="qiao_ai_target_002")

    async def _fake_execute(_statement: Any) -> _PersonaResult:
        return _PersonaResult()

    session.execute = _fake_execute  # type: ignore[attr-defined]

    payload = await panel_service.admin_reopen_ignored_contact_request(
        session,  # type: ignore[arg-type]
        request_id=100,
        operator_admin_user_id=2,
        operator_username="operator",
        operator_role=1,
    )

    assert payload["request_id"] == "100"
    assert payload["status"] == int(ContactRequestStatus.PENDING)
    assert int(row.status) == int(ContactRequestStatus.PENDING)
    assert row.failure_code == ContactRequestFailureCode.MANUAL_PROVISION_REQUIRED.value
    assert row.failure_detail == {
        "ai_type_id": 3,
        "type_id": 3,
        "qiao_id": "qiao_ai_target_002",
        "request_id": 100,
    }
    assert row.expires_at == original_expires_at
    assert session.committed is True


@pytest.mark.asyncio
async def test_admin_reopen_rejects_non_ignored_status() -> None:
    row = SimpleNamespace(
        id=101,
        status=ContactRequestStatus.FAILED,
        to_qiao_id="qiao_ai_target_003",
        to_type=2,
        expires_at=datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC),
        failure_code=None,
        failure_detail=None,
    )
    session = _ActionSession(row)

    with pytest.raises(HTTPException) as exc_info:
        await panel_service.admin_reopen_ignored_contact_request(
            session,  # type: ignore[arg-type]
            request_id=101,
            operator_admin_user_id=2,
            operator_username="operator",
            operator_role=1,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_admin_reopen_rejects_ai_request_without_resolvable_ai_type() -> None:
    row = SimpleNamespace(
        id=102,
        status=ContactRequestStatus.IGNORED,
        to_qiao_id="missing_persona_qiao_id",
        to_type=2,
        expires_at=datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC),
        failure_code=None,
        failure_detail=None,
    )
    session = _ActionSession(row)

    class _EmptyPersonaResult:
        def one_or_none(self) -> Any:
            return None

    async def _fake_execute(_statement: Any) -> _EmptyPersonaResult:
        return _EmptyPersonaResult()

    session.execute = _fake_execute  # type: ignore[attr-defined]

    with pytest.raises(HTTPException) as exc_info:
        await panel_service.admin_reopen_ignored_contact_request(
            session,  # type: ignore[arg-type]
            request_id=102,
            operator_admin_user_id=2,
            operator_username="operator",
            operator_role=1,
        )
    assert exc_info.value.status_code == 409
