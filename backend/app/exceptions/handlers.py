"""
Exception handlers for FastAPI application.

This module provides centralized exception handling for all application exceptions,
ensuring consistent error responses and proper logging.
"""

import traceback
from datetime import UTC, datetime
from typing import Any

from exceptions.base import BaseAppException
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError
from utils.logging import get_logger

logger = get_logger(__name__)


def create_error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
    path: str | None = None,
) -> JSONResponse:
    """
    Create a standardized error response.

    Args:
        error_code: Machine-readable error code
        message: Human-readable error message
        status_code: HTTP status code
        details: Additional error details
        path: Request path

    Returns:
        JSONResponse: Standardized error response
    """
    response_data = {
        "success": False,
        "error": {"code": error_code, "message": message},
        "timestamp": datetime.now(UTC).isoformat() + "Z",
    }

    if details:
        response_data["error"]["details"] = details

    if path:
        response_data["path"] = path

    return JSONResponse(status_code=status_code, content=response_data)


async def base_app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    """
    Handle custom application exceptions.

    Args:
        request: FastAPI request object
        exc: Application exception

    Returns:
        JSONResponse: Error response
    """
    logger.warning(
        "application_exception",
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        path=str(request.url.path),
        details=exc.details,
    )

    return create_error_response(
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        path=str(request.url.path),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle FastAPI request validation errors.

    Args:
        request: FastAPI request object
        exc: Validation exception

    Returns:
        JSONResponse: Error response
    """
    # Extract validation error details
    errors = []
    for error in exc.errors():
        error_detail = {
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        if "input" in error:
            error_detail["input"] = error["input"]
        errors.append(error_detail)

    logger.warning("validation_exception", path=str(request.url.path), errors=errors)

    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"errors": errors},
        path=str(request.url.path),
    )


async def pydantic_validation_exception_handler(
    request: Request, exc: PydanticValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    Args:
        request: FastAPI request object
        exc: Pydantic validation exception

    Returns:
        JSONResponse: Error response
    """
    # Extract validation error details
    errors = []
    for error in exc.errors():
        error_detail = {
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        if "input" in error:
            error_detail["input"] = error["input"]
        errors.append(error_detail)

    logger.warning("pydantic_validation_exception", path=str(request.url.path), errors=errors)

    return create_error_response(
        error_code="VALIDATION_ERROR",
        message="Data validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"errors": errors},
        path=str(request.url.path),
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """
    Handle SQLAlchemy database errors.

    Args:
        request: FastAPI request object
        exc: SQLAlchemy exception

    Returns:
        JSONResponse: Error response
    """
    logger.error("database_exception", path=str(request.url.path), error=str(exc), exc_info=True)

    # Don't expose database errors to users in production
    return create_error_response(
        error_code="DATABASE_ERROR",
        message="Database operation failed",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        path=str(request.url.path),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Args:
        request: FastAPI request object
        exc: Generic exception

    Returns:
        JSONResponse: Error response
    """
    logger.error(
        "unexpected_exception",
        path=str(request.url.path),
        error=str(exc),
        traceback=traceback.format_exc(),
        exc_info=True,
    )

    return create_error_response(
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        path=str(request.url.path),
    )


def register_exception_handlers(app) -> None:
    """
    Register all exception handlers with the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Custom application exceptions
    app.add_exception_handler(BaseAppException, base_app_exception_handler)

    # Validation exceptions
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(PydanticValidationError, pydantic_validation_exception_handler)

    # Database exceptions
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)

    # Generic exception handler (catch-all)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("exception_handlers_registered")
