"""
Admin authentication API routes.
Handles admin login and user information operations.

Note: The login endpoint is exposed via an obfuscated path (/abandoned) for security.
This is a deliberate security measure to hide the admin login endpoint from potential attackers.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.security import verify_password, create_admin_access_token
from models.admin import AdminUser
from utils.admin_logs import create_login_log
from schemas.admin.base import Success
from schemas.admin.auth import CredentialsSchema, JWTOut
from core.config import settings
from utils.logging import get_logger
from api.deps import get_current_admin_user

logger = get_logger(__name__)

# Router for admin authentication endpoints
# This router will be mounted at /abandoned for security obfuscation
auth_router = APIRouter()

# Router for admin user operations
# This router will be mounted at /admin for standard admin operations
router = APIRouter()


@auth_router.get("/health", summary="Health check")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "ok", "message": ""}


@auth_router.post("/access_token", summary="Admin login to get access token")
async def login_access_token(
    credentials: CredentialsSchema, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    Admin login endpoint.
    Authenticates admin user and returns JWT token.
    Records all login attempts for security auditing.

    Note: This endpoint is accessed via /api/v1/abandoned/access_token for security.
    """
    try:
        # Find admin user by username
        result = await db.execute(select(AdminUser).where(AdminUser.username == credentials.username))
        admin_user = result.scalar_one_or_none()

        if not admin_user:
            # Record failed login attempt - user not found
            await create_login_log(
                db=db,
                username=credentials.username,
                result=2,  # 2 = fail
                fail_reason="Admin account not found",
                request=request,
            )
            raise HTTPException(status_code=401, detail="Login failed")

        # Check if admin is active
        if admin_user.status != 1:
            # Record failed login attempt - account disabled
            await create_login_log(
                db=db,
                username=credentials.username,
                result=2,  # 2 = fail
                fail_reason="Admin account disabled",
                admin_user_id=admin_user.id,
                request=request,
            )
            raise HTTPException(status_code=401, detail="Login failed")

        # Verify password
        if not verify_password(credentials.password, admin_user.password_hash):
            # Record failed login attempt - wrong password
            await create_login_log(
                db=db,
                username=credentials.username,
                result=2,  # 2 = fail
                fail_reason="Wrong password",
                admin_user_id=admin_user.id,
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
            result=1,  # 1 = success
            admin_user_id=admin_user.id,
            request=request,
        )

        # Create JWT token using admin user ID
        access_token_expires = timedelta(minutes=settings.ADMIN_JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_admin_access_token(
            subject=str(admin_user.id), expires_delta=access_token_expires
        )

        data = JWTOut(access_token=access_token, username=admin_user.username, token_type="bearer")

        logger.info("admin_login_success", admin_id=admin_user.id, username=credentials.username)
        return Success(data=data.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin_login_error", error=str(e), username=credentials.username, exc_info=True)
        # Record failed login attempt - system error
        await create_login_log(
            db=db,
            username=credentials.username,
            result=2,  # 2 = fail
            fail_reason="System error",
            request=request,
        )
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/health", summary="Health check")
async def admin_health_check():
    """Simple health check endpoint for admin operations"""
    return {"status": "ok", "message": ""}


@router.get("/userinfo", summary="Get admin user info")
async def get_userinfo(admin_user: AdminUser = Depends(get_current_admin_user)):
    """
    Get current admin user information.
    """
    try:
        data = {
            "id": admin_user.id,
            "username": admin_user.username,
            "alias": admin_user.username,  # Use username as alias
            "role": admin_user.role,
            "role_display": admin_user.role_display,
            "is_active": admin_user.status == 1,  # Convert status to boolean
            "last_login": (
                admin_user.last_login.strftime("%Y-%m-%d %H:%M:%S") if admin_user.last_login else None
            ),
            "avatar": "https://avatars.githubusercontent.com/u/54677442?v=4",  # Default avatar
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
