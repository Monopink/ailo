"""
API response formatting utilities.
Pure functions for standardizing API response formats.
"""

from typing import Dict, Any, Optional


def format_success_response(data: Any, message: str = "操作成功") -> Dict[str, Any]:
    """
    Format successful API response.

    Args:
        data: Response data
        message: Success message

    Returns:
        Formatted success response
    """
    return {"success": True, "data": data, "message": message}


def format_error_response(
    error_code: str, error_message: str, details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format error API response.

    Args:
        error_code: Error code identifier
        error_message: Human-readable error message
        details: Optional error details

    Returns:
        Formatted error response
    """
    error_data = {"code": error_code, "message": error_message}

    if details:
        error_data["details"] = details

    return {"success": False, "error": error_data}


def format_validation_error_response(validation_errors: Dict[str, str]) -> Dict[str, Any]:
    """
    Format validation error response.

    Args:
        validation_errors: Field validation errors

    Returns:
        Formatted validation error response
    """
    return format_error_response(
        error_code="VALIDATION_ERROR",
        error_message="请求参数验证失败",
        details={"field_errors": validation_errors},
    )
