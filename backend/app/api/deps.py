"""
API dependencies for authentication and authorization.
"""

from datetime import UTC, datetime

from core.database import get_db
from crud.user import user as user_crud
from crud.user import user_token as token_crud
from fastapi import Depends, HTTPException, status
from services.security.auth_tracker import should_require_captcha
from services.security.captcha.factory import create_captcha_provider
from services.security.rate_limiter import check_message_rate_limit, check_rate_limit
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from utils.logging import get_logger

logger = get_logger(__name__)


async def verify_admin_session(request: Request) -> dict:
    """
    Verify admin session from Starlette-Admin.

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
    if not admin_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Session"},
        )
    return admin_user


async def get_admin_user_and_db(
    request: Request, db: AsyncSession = Depends(get_db)
) -> tuple[dict, AsyncSession]:
    """
    Get both admin user and database session.

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


async def require_auth_rate_limit(auth_type: str):
    """
    Authentication rate limit dependency factory.

    Args:
        auth_type: 'admin' or 'user'

    Returns:
        Dependency function
    """

    async def dependency(request: Request, db: AsyncSession = Depends(get_db)):
        ip = request.client.host if request.client else "unknown"
        allowed, error_code, retry_after = await check_rate_limit(ip, f"{auth_type}_auth", db)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": error_code,
                    "message": "操作过于频繁，请稍后再试",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


async def require_sms_rate_limit(request: Request, db: AsyncSession = Depends(get_db)):
    """SMS rate limit dependency"""

    # Get phone from request body
    body = await request.json()
    phone = body.get("phone", "")

    if not phone:
        raise HTTPException(400, detail="手机号不能为空")

    allowed, error_code, retry_after = await check_rate_limit(phone, "sms", db)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": error_code,
                "message": "短信发送过于频繁，请稍后再试",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


async def require_message_rate_limit(user_id: str, db: AsyncSession = Depends(get_db)):
    """Message rate limit dependency"""

    allowed, error_code, retry_after = await check_message_rate_limit(user_id, db)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": error_code,
                "message": "消息发送过于频繁，请稍后再试",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


async def require_captcha_if_needed(
    auth_type: str,
    token_field: str = "captcha_token",  # 'admin' or 'user'
):
    """
    Conditional CAPTCHA verification dependency factory.

    Args:
        auth_type: 'admin' or 'user'
        token_field: Field name for CAPTCHA token in request body

    Returns:
        Dependency function
    """

    async def dependency(request: Request, db: AsyncSession = Depends(get_db)):
        ip = request.client.host if request.client else "unknown"

        # Check if CAPTCHA is required
        if await should_require_captcha(ip, f"{auth_type}_auth", db):
            # Get token from request
            body = await request.json()
            token = body.get(token_field)

            if not token:
                raise HTTPException(status_code=400, detail="需要进行验证")

            # Verify token
            provider = await create_captcha_provider(auth_type, db)
            is_valid, error = await provider.verify_token(token, ip)

            if not is_valid:
                logger.warning(
                    "captcha_verification_failed", ip=ip, auth_type=auth_type, error=error
                )
                raise HTTPException(status_code=400, detail=f"验证失败: {error}")

            logger.info("captcha_verification_success", ip=ip, auth_type=auth_type)

    return dependency


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Get current authenticated user from JWT token.

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
    user_token = await token_crud.get_by_token(db, token=token)
    if not user_token:
        raise HTTPException(
            status_code=401, detail="登录失败", headers={"WWW-Authenticate": "Bearer"}
        )

    # 3. Check token status
    if user_token.status != 1:
        raise HTTPException(
            status_code=401, detail="登录失效", headers={"WWW-Authenticate": "Bearer"}
        )

    # 4. Check token expiration
    if user_token.expires_at < datetime.now(UTC):
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
            status_code=401, detail="账号已被禁用", headers={"WWW-Authenticate": "Bearer"}
        )

    # 7. Update last_activity_at
    user_token.last_activity_at = datetime.now(UTC)
    db.add(user_token)
    await db.commit()

    logger.debug("user_authenticated", qiao_id=user.qiao_id, token=token[:16] + "...")

    return user
