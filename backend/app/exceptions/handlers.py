"""Centralized exception handlers for unified API error responses."""

from __future__ import annotations

import traceback
from collections.abc import Mapping
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions.base import BaseAppError
from app.exceptions.error_codes import (
    build_error_code,
    is_protective_denial_detail,
    resolve_protective_denial_response,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
ADMIN_API_PREFIX = "/admin-api"
ADMIN_LOGIN_PATH = "/qiao-dash/login"

DEFAULT_USER_MESSAGE_BY_STATUS: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "请求参数错误",
    status.HTTP_401_UNAUTHORIZED: "登录失效",
    status.HTTP_403_FORBIDDEN: "无权操作",
    status.HTTP_404_NOT_FOUND: "资源不存在",
    status.HTTP_409_CONFLICT: "状态冲突，请稍后重试",
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "请求体过大",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "不支持的内容类型",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "请求参数错误",
    status.HTTP_428_PRECONDITION_REQUIRED: "请先完成验证",
    status.HTTP_429_TOO_MANY_REQUESTS: "操作过于频繁，请稍后再试",
}


def _is_system_status(status_code: int) -> bool:
    return status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR


def _get_or_create_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id

    header_value = request.headers.get(REQUEST_ID_HEADER) or request.headers.get(
        REQUEST_ID_HEADER.lower()
    )
    if header_value:
        request_id = header_value
    else:
        request_id = f"req_{uuid4().hex[:12]}"

    request.state.request_id = request_id
    return request_id


def _extract_user_message(detail: object | None, status_code: int) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail.strip()

    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    default = DEFAULT_USER_MESSAGE_BY_STATUS.get(status_code)
    if default is not None:
        return default
    return "请求失败，请稍后再试"


def _extract_user_reason(detail: object | None) -> str | None:
    if not isinstance(detail, dict):
        return None
    reason = detail.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    return None


def _is_admin_api_path(path: str) -> bool:
    return path == ADMIN_API_PREFIX or path.startswith(f"{ADMIN_API_PREFIX}/")


def _is_admin_login_path(path: str) -> bool:
    return path == ADMIN_LOGIN_PATH


def _get_admin_session_user(request: Request) -> Mapping[str, object] | None:
    try:
        admin_user = request.session.get("admin_user")
    except AssertionError:
        return None

    if isinstance(admin_user, dict):
        return admin_user
    return None


def _should_hide_admin_error_detail(request: Request, *, path: str) -> bool:
    if _is_admin_login_path(path):
        return True
    if not _is_admin_api_path(path):
        return False
    return _get_admin_session_user(request) is None


def _extract_admin_detail(
    detail: object | None,
    *,
    status_code: int,
    hide_detail: bool,
) -> str:
    message: str | None = None

    if hide_detail:
        if _is_system_status(status_code):
            message = "系统错误"
        else:
            default = DEFAULT_USER_MESSAGE_BY_STATUS.get(status_code)
            if default is not None:
                message = default
            else:
                message = "请求失败，请稍后再试"
        return message

    if isinstance(detail, str) and detail.strip():
        message = detail.strip()
    elif isinstance(detail, dict):
        detail_text = detail.get("detail")
        if isinstance(detail_text, str) and detail_text.strip():
            message = detail_text.strip()
        else:
            detail_message = detail.get("message")
            if isinstance(detail_message, str) and detail_message.strip():
                message = detail_message.strip()

    if message is None:
        default = DEFAULT_USER_MESSAGE_BY_STATUS.get(status_code)
        if default is not None:
            message = default
        elif _is_system_status(status_code):
            message = "系统错误"
        else:
            message = "请求失败，请稍后再试"
    return message


def _extract_admin_error_type(detail: object | None, *, hide_detail: bool) -> str | None:
    if hide_detail or not isinstance(detail, dict):
        return None
    error_type = detail.get("error_type")
    if isinstance(error_type, str) and error_type.strip():
        return error_type.strip()
    return None


def _extract_admin_debug(
    detail: object | None, *, hide_detail: bool
) -> Mapping[str, object] | None:
    if hide_detail or not isinstance(detail, dict):
        return None
    debug = detail.get("debug")
    if isinstance(debug, Mapping):
        return debug
    return None


def create_error_response(
    request: Request,
    *,
    status_code: int,
    error_code: int,
    message: str,
    reason: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Create unified error response payload."""
    request_id = _get_or_create_request_id(request)
    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = request_id

    payload: dict[str, object] = {
        "error_code": error_code,
        "message": message,
        "request_id": request_id,
    }
    if reason is not None:
        payload["reason"] = reason

    return JSONResponse(status_code=status_code, content=payload, headers=response_headers)


def create_admin_error_response(
    request: Request,
    *,
    status_code: int,
    detail: str,
    headers: Mapping[str, str] | None = None,
    error_type: str | None = None,
    debug: Mapping[str, object] | None = None,
) -> JSONResponse:
    """Create admin API error response payload."""
    request_id = _get_or_create_request_id(request)
    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = request_id

    payload: dict[str, object] = {
        "detail": detail,
        "request_id": request_id,
    }
    if error_type is not None:
        payload["error_type"] = error_type
    if debug is not None:
        payload["debug"] = debug

    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers=response_headers,
    )


def _build_response(
    request: Request,
    *,
    status_code: int,
    detail: object | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    path = request.url.path
    hide_admin_detail = _should_hide_admin_error_detail(request, path=path)
    use_admin_error_shape = _is_admin_api_path(path)

    if is_protective_denial_detail(detail):
        protective_status, protective_message = resolve_protective_denial_response(detail)
        if use_admin_error_shape:
            return create_admin_error_response(
                request,
                status_code=protective_status,
                detail=_extract_admin_detail(
                    protective_message,
                    status_code=protective_status,
                    hide_detail=hide_admin_detail,
                ),
                headers=headers,
            )
        protective_error_code = build_error_code(
            path=path,
            status_code=protective_status,
            detail=protective_message,
        )
        return create_error_response(
            request,
            status_code=protective_status,
            error_code=protective_error_code,
            message=protective_message,
        )

    if use_admin_error_shape:
        return create_admin_error_response(
            request,
            status_code=status_code,
            detail=_extract_admin_detail(
                detail,
                status_code=status_code,
                hide_detail=hide_admin_detail,
            ),
            headers=headers,
            error_type=_extract_admin_error_type(detail, hide_detail=hide_admin_detail),
            debug=_extract_admin_debug(detail, hide_detail=hide_admin_detail),
        )

    error_code = build_error_code(path=path, status_code=status_code, detail=detail)

    if _is_system_status(status_code):
        message = f"系统错误（{error_code}）"
    else:
        message = _extract_user_message(detail=detail, status_code=status_code)

    return create_error_response(
        request,
        status_code=status_code,
        error_code=error_code,
        message=message,
        reason=None if _is_system_status(status_code) else _extract_user_reason(detail),
        headers=headers,
    )


async def base_app_exception_handler(request: Request, exc: BaseAppError) -> Response:
    """Handle custom application exceptions."""
    request_id = _get_or_create_request_id(request)
    if _is_system_status(exc.status_code):
        logger.error(
            "application_exception",
            request_id=request_id,
            path=request.url.path,
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )
    else:
        logger.warning(
            "application_exception",
            request_id=request_id,
            path=request.url.path,
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )

    return _build_response(request, status_code=exc.status_code, detail=exc.message)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """Handle framework HTTP exceptions."""
    request_id = _get_or_create_request_id(request)
    if _is_system_status(exc.status_code):
        logger.error(
            "http_exception",
            request_id=request_id,
            path=request.url.path,
            status_code=exc.status_code,
            detail=exc.detail,
        )
    else:
        logger.warning(
            "http_exception",
            request_id=request_id,
            path=request.url.path,
            status_code=exc.status_code,
            detail=exc.detail,
        )

    return _build_response(
        request,
        status_code=exc.status_code,
        detail=exc.detail,
        headers=exc.headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> Response:
    """Handle request validation failures."""
    request_id = _get_or_create_request_id(request)
    logger.warning(
        "validation_exception",
        request_id=request_id,
        path=request.url.path,
        errors=exc.errors(),
    )
    return _build_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="请求参数错误",
    )


async def pydantic_validation_exception_handler(
    request: Request, exc: PydanticValidationError
) -> Response:
    """Handle Pydantic validation failures."""
    request_id = _get_or_create_request_id(request)
    logger.warning(
        "pydantic_validation_exception",
        request_id=request_id,
        path=request.url.path,
        errors=exc.errors(),
    )
    return _build_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="请求参数错误",
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> Response:
    """Handle database exceptions."""
    request_id = _get_or_create_request_id(request)
    logger.error(
        "database_exception",
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return _build_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "message": str(exc),
            "error_type": exc.__class__.__name__,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> Response:
    """Handle uncaught exceptions."""
    request_id = _get_or_create_request_id(request)
    logger.error(
        "unexpected_exception",
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
        traceback=traceback.format_exc(),
        exc_info=True,
    )
    return _build_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "message": str(exc),
            "error_type": exc.__class__.__name__,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers for unified error format."""
    app.add_exception_handler(BaseAppError, base_app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(PydanticValidationError, pydantic_validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)
    logger.info("exception_handlers_registered")
