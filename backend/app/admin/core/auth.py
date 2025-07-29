"""
Admin authentication and authorization system.
Integrates with main project's JWT authentication.
"""

import sys
import os
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.security import decode_access_token

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from admin.models import AdminUser
from admin.settings import admin_settings
from utils.logging import get_logger

logger = get_logger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


class AdminAuthControl:
    """Admin authentication control - independent admin user system"""

    @staticmethod
    async def get_current_admin_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db),
    ) -> AdminUser:
        """
        Get current authenticated admin user from JWT token.
        Uses independent admin user system.
        """
        try:
            token = credentials.credentials
            logger.debug("admin_auth_attempt", token_length=len(token))

            # Decode JWT token
            payload = decode_access_token(token)
            if payload is None:
                logger.warning("admin_auth_failed", reason="invalid_token")
                raise HTTPException(status_code=401, detail="Invalid token")

            admin_id_str: str = payload.get("sub")
            if admin_id_str is None:
                logger.warning("admin_auth_failed", reason="missing_sub", payload=payload)
                raise HTTPException(status_code=401, detail="Invalid token payload")

            # Convert admin_id to integer
            try:
                admin_id = int(admin_id_str)
            except ValueError:
                raise HTTPException(status_code=401, detail="Invalid token format")

            # Get admin user from database
            result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
            admin_user = result.scalar_one_or_none()

            if admin_user is None:
                raise HTTPException(status_code=401, detail="Admin user not found")

            if not admin_user.is_active:
                raise HTTPException(status_code=401, detail="Admin account is disabled")

            return admin_user

        except HTTPException:
            raise
        except Exception as e:
            logger.error("admin_auth_error", error=str(e), exc_info=True)
            raise HTTPException(status_code=401, detail="Authentication failed")

    @staticmethod
    async def get_admin_user(
        admin_user: AdminUser = Depends(get_current_admin_user), db: AsyncSession = None
    ) -> AdminUser:
        """
        Get admin user - simplified since we use independent admin users.
        This method is now just a passthrough for compatibility.
        """
        return admin_user


class AdminPermissionControl:
    """Admin permission control"""

    @staticmethod
    async def check_permission(
        request: Request,
        admin_user: AdminUser = None,
        db: AsyncSession = None,
    ) -> None:
        """
        Simplified permission check - only verifies user is active.
        Specific permissions should be handled by decorators on individual endpoints.
        """
        try:
            # Check if user is active
            if not admin_user.is_active:
                raise HTTPException(status_code=403, detail="Account is disabled")

            # Log successful permission check
            logger.debug(
                "admin_permission_granted",
                admin_user_id=admin_user.id,
                role=admin_user.role,
                method=request.method,
                path=request.url.path,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("check_permission_error", error=str(e), exc_info=True)
            raise HTTPException(status_code=500, detail="Permission check failed")


# Independent dependency functions to avoid circular references
async def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """Get current authenticated admin user from JWT token"""
    return await AdminAuthControl.get_current_admin_user(credentials, db)


async def get_admin_user(
    admin_user: AdminUser = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """Get admin user - simplified passthrough for compatibility"""
    return await AdminAuthControl.get_admin_user(admin_user, db)


async def check_permission(
    request: Request,
    admin_user: AdminUser = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Check if admin user has permission for the requested API"""
    return await AdminPermissionControl.check_permission(request, admin_user, db)


# Dependency shortcuts - these are functions, not Depends objects
GetCurrentUser = get_current_admin_user  # For compatibility, use admin user
GetAdminUser = get_admin_user
CheckPermission = check_permission
