"""Password login failure behavior contract tests."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1 import auth as auth_api
from app.enums import DeviceType
from app.schemas.auth import PasswordLoginRequest


def _build_request() -> Request:
    """Build a minimal HTTP request object for endpoint unit tests."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": [(b"x-client-ip", b"203.0.113.10")],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_password_login_invalid_credentials_returns_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid credentials should return a normal business error, not protective denial."""
    monkeypatch.setattr(auth_api, "check_lockout", AsyncMock(return_value=(False, None)))
    monkeypatch.setattr(
        auth_api, "check_password_login_rate_limit", AsyncMock(return_value=(True, None, None))
    )
    monkeypatch.setattr("app.api.v1.auth.user_crud.authenticate", AsyncMock(return_value=None))
    monkeypatch.setattr(auth_api, "_record_login_attempt", AsyncMock())
    monkeypatch.setattr(auth_api, "record_auth_failure", AsyncMock())
    credential = uuid4().hex

    body = PasswordLoginRequest(
        identifier="not_exists_user",
        password=credential,
        device_id=uuid4(),
        device_type=DeviceType.WEB,
    )
    fake_db: Any = object()  # reason: endpoint branch unit test does not touch db methods

    with pytest.raises(HTTPException) as exc_info:
        await auth_api.password_login(_build_request(), body, db=fake_db)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "账号或密码错误"


@pytest.mark.asyncio
async def test_password_login_inactive_user_returns_status_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inactive accounts should return a clear status error message."""
    monkeypatch.setattr(auth_api, "check_lockout", AsyncMock(return_value=(False, None)))
    monkeypatch.setattr(
        auth_api, "check_password_login_rate_limit", AsyncMock(return_value=(True, None, None))
    )
    monkeypatch.setattr(
        "app.api.v1.auth.user_crud.authenticate",
        AsyncMock(return_value=SimpleNamespace(id=1, qiao_id="qiao_test")),
    )
    monkeypatch.setattr("app.api.v1.auth.user_crud.is_active", AsyncMock(return_value=False))
    monkeypatch.setattr(auth_api, "_record_login_attempt", AsyncMock())
    monkeypatch.setattr(auth_api, "record_auth_failure", AsyncMock())
    credential = uuid4().hex

    body = PasswordLoginRequest(
        identifier="inactive_user",
        password=credential,
        device_id=uuid4(),
        device_type=DeviceType.WEB,
    )
    fake_db: Any = object()  # reason: endpoint branch unit test does not touch db methods

    with pytest.raises(HTTPException) as exc_info:
        await auth_api.password_login(_build_request(), body, db=fake_db)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "账号状态异常"
