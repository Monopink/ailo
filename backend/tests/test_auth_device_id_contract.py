"""Auth request contract tests for mandatory UUID device_id and stable session_id."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.enums import DeviceType
from app.schemas.auth import (
    PasswordLoginRequest,
    VerifyPhoneRequest,
    WeChatBindPhoneRequest,
    WeChatLoginRequest,
)
from app.utils.token import decode_jwt_token, generate_jwt_token


def test_password_login_request_requires_uuid_device_id() -> None:
    """Password login rejects non-UUID device_id values."""
    credential = __name__
    invalid_device_id: Any = "not-a-uuid"  # reason: negative validation test input
    with pytest.raises(ValidationError):
        PasswordLoginRequest(
            identifier="alice",
            password=credential,
            device_id=invalid_device_id,
            device_type=DeviceType.WEB,
        )


def test_wechat_requests_require_uuid_device_id() -> None:
    """WeChat login/bind requests reject non-UUID device_id values."""
    invalid_device_id: Any = "not-a-uuid"  # reason: negative validation test input
    with pytest.raises(ValidationError):
        WeChatLoginRequest(login_code="code", device_id=invalid_device_id)

    with pytest.raises(ValidationError):
        WeChatBindPhoneRequest(
            login_code="code",
            phone_code="phone_code",
            device_id=invalid_device_id,
        )


def test_verify_phone_request_requires_uuid_device_id() -> None:
    """Phone login request rejects non-UUID device_id values."""
    invalid_device_id: Any = "not-a-uuid"  # reason: negative validation test input
    with pytest.raises(ValidationError):
        VerifyPhoneRequest(
            phone="+8613800138000",
            sms_code="123456",
            device_id=invalid_device_id,
        )


def test_generate_jwt_token_uses_stable_session_id() -> None:
    """JWT payload session_id must match the provided stable session id."""
    session_id = 281604671221665793
    token = generate_jwt_token(
        user_id=281306038819491840,
        qiao_id="qiao_9ZKSyTeEtDEMLWF0",
        device_type=DeviceType.WEB,
        expires_in_seconds=3600,
        session_id=session_id,
    )

    payload = decode_jwt_token(token)
    assert payload is not None
    assert payload["session_id"] == session_id
