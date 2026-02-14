"""Contract tests for unified API error code behavior."""

from __future__ import annotations

import json
from typing import cast

from fastapi import status
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.ws.messages import _build_ws_error_payload
from app.exceptions.error_codes import build_error_code, build_protective_denial_detail
from app.exceptions.handlers import _build_response


def _build_request(path: str, *, session_data: dict[str, object] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "server": ("test", 80),
        "query_string": b"",
    }
    if session_data is not None:
        scope["session"] = session_data
    return Request(scope)


def _payload(response: JSONResponse) -> dict[str, object]:
    raw_body = response.body
    if isinstance(raw_body, memoryview):
        raw_bytes = raw_body.tobytes()
    else:
        raw_bytes = raw_body
    return cast(dict[str, object], json.loads(raw_bytes.decode("utf-8")))


def test_error_code_is_8_digits_for_auth_business_error() -> None:
    code = build_error_code(
        path="/api/v1/auth/login",
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="账号或密码错误",
    )
    assert code == 11011005
    assert len(str(code)) == 8


def test_error_code_resolution_decouples_from_http_status() -> None:
    code_400 = build_error_code(
        path="/api/v1/auth/login",
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="账号或密码错误",
    )
    code_429 = build_error_code(
        path="/api/v1/auth/login",
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="账号或密码错误",
    )
    assert code_400 == code_429


def test_protective_denial_reuses_normal_business_error_tuple() -> None:
    request = _build_request("/api/v1/auth/login")

    protective_detail = build_protective_denial_detail(
        reason="AUTH_LOCKED_OUT",
        camouflage_status_code=status.HTTP_400_BAD_REQUEST,
        camouflage_message="登录失败，请稍后再试",
        metadata={"retry_after": 123},
    )
    protective = _build_response(
        request,
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=protective_detail,
    )
    protective_payload = _payload(protective)

    expected_error_code = build_error_code(
        path="/api/v1/auth/login",
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="登录失败，请稍后再试",
    )
    assert protective.status_code == status.HTTP_400_BAD_REQUEST
    assert protective_payload["error_code"] == expected_error_code
    assert protective_payload["message"] == "登录失败，请稍后再试"


def test_5xx_message_always_embeds_error_code() -> None:
    request = _build_request("/api/v1/system/captcha-config")
    response = _build_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="数据库连接失败",
    )
    payload = _payload(response)

    error_code = payload["error_code"]
    assert isinstance(error_code, int)
    assert len(str(error_code)) == 8
    assert payload["message"] == f"系统错误（{error_code}）"
    assert response.headers["X-Request-ID"] == payload["request_id"]


def test_ws_handshake_uses_ws_module_prefix() -> None:
    code = build_error_code(
        path="/ws/messages",
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证失效，请重新登录",
    )
    assert str(code).startswith("2403")


def test_ws_error_frame_payload_uses_unified_error_fields() -> None:
    payload = _build_ws_error_payload(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="需要先登录",
    )

    assert payload["error_code"] == 24032001
    assert payload["message"] == "需要先登录"
    assert isinstance(payload["request_id"], str)
    assert str(payload["request_id"]).startswith("req_")


def test_ws_error_frame_5xx_message_is_masked() -> None:
    payload = _build_ws_error_payload(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="系统配置异常",
    )

    error_code = payload["error_code"]
    assert error_code == 24039001
    assert payload["message"] == f"系统错误（{error_code}）"


def test_admin_message_detail_is_registered_explicitly() -> None:
    code = build_error_code(
        path="/admin-api/ai/template",
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="prompt_variables must be a dict",
    )
    assert code == 80011001


def test_admin_api_response_uses_detail_shape_after_login() -> None:
    request = _build_request(
        "/admin-api/ai/style/1/save",
        session_data={"admin_user": {"id": 1, "username": "admin", "role": 1}},
    )
    response = _build_response(
        request,
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="dimension name already exists",
    )
    payload = _payload(response)

    assert payload["detail"] == "dimension name already exists"
    assert isinstance(payload["request_id"], str)
    assert "error_code" not in payload
    assert "message" not in payload


def test_admin_api_response_hides_detail_when_not_logged_in() -> None:
    request = _build_request("/admin-api/ai/style/1/save", session_data={})
    response = _build_response(
        request,
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
    payload = _payload(response)

    assert payload["detail"] == "登录失效"
    assert isinstance(payload["request_id"], str)
    assert "debug" not in payload


def test_admin_api_response_allows_error_type_after_login() -> None:
    request = _build_request(
        "/admin-api/system/test",
        session_data={"admin_user": {"id": 1, "username": "admin", "role": 1}},
    )
    response = _build_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"message": "db failed", "error_type": "SQLAlchemyError"},
    )
    payload = _payload(response)

    assert payload["detail"] == "db failed"
    assert payload["error_type"] == "SQLAlchemyError"
