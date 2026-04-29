"""API dependencies for authentication and authorization."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.database import get_db
from app.crud.user import user as user_crud
from app.crud.user import user_token as token_crud
from app.exceptions.error_codes import build_protective_denial_detail
from app.models.user import User
from app.services.security.rate_limiter import check_message_rate_limit, check_rate_limit
from app.utils.client_ip import ClientIPResolutionError, get_client_ip
from app.utils.logging import get_logger

__all__ = [
    "verify_admin_session",
    "get_admin_user_and_db",
    "require_auth_rate_limit",
    "require_sms_rate_limit",
    "require_message_rate_limit",
    "get_current_user",
    "get_current_user_optional",
    "get_db",
]

DBSession = Annotated[AsyncSession, Depends(get_db)]

logger = get_logger(__name__)


def _protective_denial_detail(
    *,
    reason: str,
    camouflage_message: str = "操作异常",
    camouflage_status_code: int = status.HTTP_400_BAD_REQUEST,
    **metadata: object,
) -> dict[str, object]:
    """Create detail payload for protective-denial responses."""
    detail_metadata = metadata or None
    return build_protective_denial_detail(
        reason=reason,
        camouflage_status_code=camouflage_status_code,
        camouflage_message=camouflage_message,
        metadata=detail_metadata,
    )


def _resolve_client_ip(request: Request) -> str:
    """Resolve client IP from trusted proxy context for security dependencies."""
    try:
        return get_client_ip(request)
    except ClientIPResolutionError as exc:
        logger.warning("dependency_client_ip_invalid", reason=exc.reason, detail=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_protective_denial_detail(
                reason="INVALID_CLIENT_IP_DEP",
                camouflage_message="操作异常",
            ),
        ) from exc


async def verify_admin_session(request: Request) -> dict[str, Any]:
    """Verify admin session from Starlette-Admin.

    This reuses the same session authentication as the admin dashboard.
    All admin API endpoints should use this dependency for authentication.

    Args:
        request: Starlette request object

    Returns:
        dict: Admin user data from session
            {
                "id": int,
                "username": str,
                "role": int,
                "role_display": str
            }

    Raises:
        HTTPException: 401 if not authenticated

    """
    admin_user = request.session.get("admin_user")
    if not admin_user or not isinstance(admin_user, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Session"},
        )
    # Type guard to ensure admin_user is a dict, then cast for typing clarity
    return cast(dict[str, Any], admin_user)


async def get_admin_user_and_db(
    request: Request, db: DBSession
) -> tuple[dict[str, Any], AsyncSession]:
    """Get both admin user and database session.

    Convenience dependency that combines verify_admin_session and get_db.

    Args:
        request: Starlette request object
        db: Database session

    Returns:
        tuple: (admin_user, db)

    """
    admin_user = await verify_admin_session(request)
    return admin_user, db


# Security dependencies


async def require_auth_rate_limit(
    auth_type: str,
) -> Callable[[Request, AsyncSession], Awaitable[None]]:
    """Create authentication rate limit dependency factory.

    Args:
        auth_type: 'admin'

    Returns:
        Dependency function that validates rate limits for auth operations.

    Raises:
        HTTPException: 429 if rate limit exceeded

    """
    if auth_type != "admin":
        # User password login has its own dedicated security strategy
        # (see auth/login-security spec).
        raise ValueError(f"Unsupported auth_type for require_auth_rate_limit: {auth_type}")

    async def dependency(request: Request, db: DBSession) -> None:
        ip = _resolve_client_ip(request)
        allowed, error_code, retry_after = await check_rate_limit(ip, f"{auth_type}_auth", db)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_protective_denial_detail(
                    reason="ADMIN_AUTH_RATE_LIMIT",
                    camouflage_message="Authentication required",
                    limiter_error=error_code,
                    retry_after=retry_after,
                ),
            )

    return dependency


async def require_sms_rate_limit(request: Request, db: DBSession) -> None:
    """SMS rate limit dependency.

    Validates rate limits for SMS verification code sending.

    Args:
        request: FastAPI request object
        db: Database session

    Raises:
        HTTPException: 400 if phone missing, 429 if rate limit exceeded

    """
    # Get phone from request body
    body = await request.json()
    phone = body.get("phone", "")

    if not phone:
        raise HTTPException(400, detail="手机号不能为空")

    allowed, error_code, retry_after = await check_rate_limit(phone, "sms", db)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_protective_denial_detail(
                reason="SMS_RATE_LIMIT_DEP",
                camouflage_message="请30秒后再试",
                limiter_error=error_code,
                retry_after=retry_after,
            ),
        )


async def require_message_rate_limit(user_id: str, db: DBSession) -> None:
    """Message rate limit dependency.

    Validates rate limits for message sending operations.

    Args:
        user_id: User ID (qiao_id)
        db: Database session

    Raises:
        HTTPException: 429 if rate limit exceeded

    """
    allowed, error_code, retry_after = await check_message_rate_limit(user_id, db)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_protective_denial_detail(
                reason="MESSAGE_RATE_LIMIT_DEP",
                camouflage_message="请求过于频繁，请稍后再试",
                limiter_error=error_code,
                retry_after=retry_after,
            ),
        )


async def get_current_user(request: Request, db: DBSession) -> User:
    """Get current authenticated user from JWT token.

    Args:
        request: FastAPI request
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: 401 if not authenticated or token invalid

    """
    # 1. Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="登录失败", headers={"WWW-Authenticate": "Bearer"}
        )

    token = auth_header[7:]  # Remove "Bearer " prefix

    # 2. Get token from database
    user_token = await token_crud.get_by_access_token(db, token=token)
    if not user_token:
        raise HTTPException(
            status_code=401, detail="登录失败", headers={"WWW-Authenticate": "Bearer"}
        )

    # 3. Check token status
    if user_token.status != 1 or user_token.access_revoked_at is not None:
        raise HTTPException(
            status_code=401, detail="登录失效", headers={"WWW-Authenticate": "Bearer"}
        )

    # 4. Check token expiration
    if user_token.access_expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=401, detail="登录失效", headers={"WWW-Authenticate": "Bearer"}
        )

    # 5. Get user
    user = await user_crud.get_by_qiao_id(db, qiao_id=user_token.user_qiao_id)
    if not user:
        raise HTTPException(
            status_code=401, detail="用户不存在", headers={"WWW-Authenticate": "Bearer"}
        )

    # 6. Check user status
    if not await user_crud.is_active(user):
        raise HTTPException(
            status_code=401, detail="账号状态异常", headers={"WWW-Authenticate": "Bearer"}
        )

    # 7. Update last_activity_at
    user_token.last_activity_at = datetime.now(UTC)
    db.add(user_token)

    logger.debug("user_authenticated", qiao_id=user.qiao_id)

    return user


async def get_current_user_optional(request: Request, db: DBSession) -> User | None:
    """Get current user when bearer token is valid, otherwise return None."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None
