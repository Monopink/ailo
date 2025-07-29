"""
Admin base API routes.
Handles authentication and basic user operations.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.security import verify_password, create_access_token
from admin.models import AdminUser
from admin.core.auth import GetAdminUser
from admin.core.operation_log import create_login_log
from admin.schemas.base import Success
from admin.schemas.login import CredentialsSchema, JWTOut
from admin.settings import admin_settings
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "ok", "message": ""}


@router.post("/access_token", summary="Admin login to get access token")
async def login_access_token(
    credentials: CredentialsSchema, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    Admin login endpoint.
    Authenticates admin user and returns JWT token.
    Records all login attempts for security auditing.
    """
    try:
        # Find admin user by username or email
        result = await db.execute(
            select(AdminUser).where(
                (AdminUser.username == credentials.username) | (AdminUser.email == credentials.username)
            )
        )
        admin_user = result.scalar_one_or_none()

        if not admin_user:
            # Record failed login attempt - user not found
            await create_login_log(
                db=db,
                username=credentials.username,
                login_result="FAILED",
                failure_reason="Admin account not found",
                request=request,
            )
            raise HTTPException(status_code=401, detail="Login failed")

        # Verify password
        if not verify_password(credentials.password, admin_user.password_hash):
            # Record failed login attempt - wrong password
            await create_login_log(
                db=db,
                username=credentials.username,
                login_result="FAILED",
                admin_user_id=admin_user.id,
                failure_reason="Invalid password",
                request=request,
            )
            raise HTTPException(status_code=401, detail="Login failed")

        # Check if admin user is active
        if not admin_user.is_active:
            # Record failed login attempt - account disabled
            await create_login_log(
                db=db,
                username=credentials.username,
                login_result="FAILED",
                admin_user_id=admin_user.id,
                failure_reason="Admin account disabled",
                request=request,
            )
            raise HTTPException(status_code=401, detail="Login failed")

        # Update last login
        admin_user.last_login = datetime.now()
        admin_user.login_count = (admin_user.login_count or 0) + 1
        await db.commit()

        # Record successful login
        await create_login_log(
            db=db,
            username=credentials.username,
            login_result="SUCCESS",
            admin_user_id=admin_user.id,
            request=request,
        )

        # Create JWT token using admin user ID
        access_token_expires = timedelta(minutes=admin_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(subject=str(admin_user.id), expires_delta=access_token_expires)

        data = JWTOut(access_token=access_token, username=admin_user.username, token_type="bearer")

        logger.info("admin_login_success", admin_id=admin_user.id, username=credentials.username)
        return Success(data=data.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        # Record system error login failure
        await create_login_log(
            db=db,
            username=credentials.username,
            login_result="FAILED",
            failure_reason=f"System error: {str(e)}",
            request=request,
        )
        logger.error("admin_login_error", username=credentials.username, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/userinfo", summary="Get admin user info")
async def get_userinfo(admin_user: AdminUser = Depends(GetAdminUser)):
    """
    Get current admin user information.
    """
    try:
        data = {
            "id": admin_user.id,
            "username": admin_user.username,
            "alias": admin_user.real_name or admin_user.username,  # Use real_name as alias
            "email": admin_user.email,
            "phone": admin_user.phone,
            "role": admin_user.role,
            "role_display": admin_user.role_display,
            "is_active": admin_user.is_active,
            "last_login": (
                admin_user.last_login.strftime("%Y-%m-%d %H:%M:%S") if admin_user.last_login else None
            ),
            "avatar": admin_user.avatar_url or "https://avatars.githubusercontent.com/u/54677442?v=4",
        }
        return Success(data=data)

    except Exception as e:
        logger.error("get_userinfo_error", admin_user_id=admin_user.id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get user information")


# TODO: Implement password update functionality when needed
# @router.post("/update_password", summary="Update password")
# async def update_user_password(req_in: UpdatePassword, admin_user: AdminUser = GetAdminUser):
#     """Update admin user password"""
#     pass
