"""
Operation log utilities for admin module.
Provides decorators and functions for logging admin operations.
"""

import sys
import os
from functools import wraps
from typing import Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

# Add the parent directory to the path to import from main project
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from admin.models.logs import AdminOperationLog, AdminLoginLog

from utils.logging import get_logger

logger = get_logger(__name__)


async def create_operation_log(
    db: AsyncSession,
    admin_user_id: int,
    operation_type: str,
    resource_type: str,
    operation_desc: str,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    request: Optional[Request] = None,
) -> None:
    """
    Create an operation log entry.

    Args:
        db: Database session
        admin_user_id: ID of the admin user performing the operation
        operation_type: Type of operation (CREATE, UPDATE, DELETE, ENABLE, DISABLE)
        resource_type: Type of resource being operated on
        operation_desc: Description of the operation
        resource_id: ID of the resource (optional)
        resource_name: Name of the resource (optional)
        request: FastAPI request object for IP and user agent (optional)
    """
    try:
        log_data = {
            "admin_user_id": admin_user_id,
            "operation_type": operation_type,
            "resource_type": resource_type,
            "operation_desc": operation_desc,
            "resource_id": resource_id,
            "resource_name": resource_name,
        }

        # Extract IP and user agent from request if available
        if request:
            log_data["ip_address"] = getattr(request.client, "host", None) if request.client else None
            log_data["user_agent"] = request.headers.get("user-agent", "")

        # Create log entry
        log_entry = AdminOperationLog(**log_data)
        db.add(log_entry)
        await db.commit()

        logger.info(
            "operation_log_created",
            admin_user_id=admin_user_id,
            operation_type=operation_type,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    except Exception as e:
        # Log creation failure is non-fatal but should be visible
        logger.error(
            "create_operation_log_failed",
            error=str(e),
            admin_user_id=admin_user_id,
            operation_type=operation_type,
            resource_type=resource_type,
            exc_info=True,
        )
        try:
            await db.rollback()
        except Exception as rollback_error:
            logger.error("operation_log_rollback_failed", error=str(rollback_error))


async def create_login_log(
    db: AsyncSession,
    username: str,
    login_result: str,
    admin_user_id: Optional[int] = None,
    failure_reason: Optional[str] = None,
    request: Optional[Request] = None,
) -> None:
    """
    Create a login log entry.

    Args:
        db: Database session
        username: Username used for login attempt
        login_result: Result of login (SUCCESS or FAILED)
        admin_user_id: ID of admin user (None for failed logins with invalid username)
        failure_reason: Reason for failure (if applicable)
        request: FastAPI request object for IP and user agent (optional)
    """
    try:
        # Truncate failure_reason to fit database field limit (200 chars)
        truncated_failure_reason = failure_reason[:200] if failure_reason else None

        log_data = {
            "username": username,
            "login_result": login_result,
            "admin_user_id": admin_user_id,
            "failure_reason": truncated_failure_reason,
        }

        # Extract IP and user agent from request if available
        if request:
            log_data["ip_address"] = getattr(request.client, "host", None) if request.client else None
            log_data["user_agent"] = request.headers.get("user-agent", "")

        # Create log entry
        log_entry = AdminLoginLog(**log_data)
        db.add(log_entry)
        await db.commit()

        logger.info(
            "login_log_created", username=username, login_result=login_result, admin_user_id=admin_user_id
        )

    except Exception as e:
        # Login log creation failure is non-fatal but should be visible
        logger.error(
            "create_login_log_failed",
            error=str(e),
            username=username,
            login_result=login_result,
            admin_user_id=admin_user_id,
            exc_info=True,
        )
        try:
            await db.rollback()
        except Exception as rollback_error:
            logger.error("login_log_rollback_failed", error=str(rollback_error))


def log_operation(operation_type: str, resource_type: str, description_template: str = ""):
    """
    Decorator for logging admin operations.

    Args:
        operation_type: Type of operation (CREATE, UPDATE, DELETE, ENABLE, DISABLE)
        resource_type: Type of resource being operated on
        description_template: Template for operation description

    Usage:
        @log_operation("CREATE", "admin_user", "Create admin user")
        async def create_user(...):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute the original function first
            result = await func(*args, **kwargs)

            # Extract necessary information from kwargs
            current_admin = kwargs.get("current_admin")
            db = kwargs.get("db")
            request = kwargs.get("request")

            # Only log if we have the required information
            if current_admin and db:
                try:
                    # Generate description
                    description = description_template or f"{operation_type} {resource_type}"

                    # Try to extract resource information from result or kwargs
                    resource_id = None
                    resource_name = None

                    # Check if result has data with id/name
                    if hasattr(result, "data") and result.data:
                        if isinstance(result.data, dict):
                            resource_id = result.data.get("id")
                            resource_name = (
                                result.data.get("name")
                                or result.data.get("username")
                                or result.data.get("nickname")
                            )
                        else:
                            resource_id = getattr(result.data, "id", None)
                            resource_name = (
                                getattr(result.data, "name", None)
                                or getattr(result.data, "username", None)
                                or getattr(result.data, "nickname", None)
                            )

                    # Fallback to kwargs for resource information
                    if not resource_id:
                        resource_id = (
                            kwargs.get("id")
                            or kwargs.get("user_id")
                            or kwargs.get("role_id")
                            or kwargs.get("menu_id")
                            or kwargs.get("api_id")
                            or kwargs.get("dept_id")
                        )

                    # Create the operation log
                    await create_operation_log(
                        db=db,
                        admin_user_id=current_admin.id,
                        operation_type=operation_type,
                        resource_type=resource_type,
                        operation_desc=description,
                        resource_id=str(resource_id) if resource_id else None,
                        resource_name=resource_name,
                        request=request,
                    )

                except Exception as e:
                    # Operation logging failure is non-fatal but should be visible
                    logger.error(
                        "log_operation_decorator_failed",
                        error=str(e),
                        operation_type=operation_type,
                        resource_type=resource_type,
                        admin_user_id=current_admin.id if current_admin else None,
                        exc_info=True,
                    )

            return result

        return wrapper

    return decorator
