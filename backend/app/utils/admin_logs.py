"""Admin logging utilities.

Provides both operation logging and login logging functionality.
"""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminLoginLog, AdminOperationLog
from app.utils.client_ip import get_client_ip
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def create_operation_log(
    db: AsyncSession,
    admin_user_id: int,
    operation_type: int,
    resource_type: str,
    operation_desc: str,
    resource_id: str | None = None,
    resource_name: str | None = None,
    request: Request | None = None,
) -> None:
    """Create an operation log entry.

    Args:
        db: Database session
        admin_user_id: ID of the admin user performing the operation
        operation_type: Type of operation (1=CREATE, 2=UPDATE, 3=DELETE, 4=ENABLE, 5=DISABLE)
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
            log_data["ip_address"] = get_client_ip(request)
            log_data["user_agent"] = request.headers.get("user-agent", "")

        # Create log entry
        log_entry = AdminOperationLog(**log_data)
        db.add(log_entry)
        await db.commit()

        logger.info(
            "operation_log_created", admin_user_id=admin_user_id, operation_type=operation_type
        )

    except Exception as e:
        logger.error(
            "create_operation_log_failed", error=str(e), admin_user_id=admin_user_id, exc_info=True
        )
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "operation_log_rollback_failed",
                error=str(rollback_exc),
                admin_user_id=admin_user_id,
            )


async def create_login_log(
    db: AsyncSession,
    username: str,
    result: int,
    admin_user_id: int | None = None,
    fail_reason: str | None = None,
    request: Request | None = None,
) -> None:
    """Create a login log entry.

    Args:
        db: Database session
        username: Username used for login attempt
        result: Result of login (1=success, 2=fail)
        admin_user_id: ID of admin user (None for failed logins with invalid username)
        fail_reason: Reason for failure (if applicable)
        request: FastAPI request object for IP and user agent (optional)

    """
    try:
        log_data = {
            "username": username,
            "result": result,
            "admin_user_id": admin_user_id,
            "fail_reason": fail_reason[:200] if fail_reason else None,
        }

        # Extract IP and user agent from request if available
        if request:
            log_data["ip_address"] = get_client_ip(request)
            log_data["user_agent"] = request.headers.get("user-agent", "")

        # Create log entry
        log_entry = AdminLoginLog(**log_data)
        db.add(log_entry)
        await db.commit()

        logger.info("login_log_created", username=username, result=result)

    except Exception as e:
        logger.error("create_login_log_failed", error=str(e), username=username, exc_info=True)
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "login_log_rollback_failed",
                error=str(rollback_exc),
                username=username,
            )
