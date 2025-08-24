"""
API dependencies for authentication and authorization.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.security import decode_access_token
from models.admin import AdminUser
from utils.logging import get_logger

logger = get_logger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """
    Get current authenticated admin user from JWT token.

    Args:
        credentials: HTTP Bearer credentials containing JWT token
        db: Database session

    Returns:
        AdminUser: The authenticated admin user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        token = credentials.credentials
        logger.debug("admin_auth_attempt", token_length=len(token))

        # Decode JWT token
        payload = decode_access_token(token)
        if payload is None:
            logger.warning("admin_auth_failed", reason="invalid_token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        admin_id_str: str = payload.get("sub")
        if admin_id_str is None:
            logger.warning("admin_auth_failed", reason="missing_subject")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Convert admin ID to integer
        try:
            admin_id = int(admin_id_str)
        except ValueError:
            logger.warning("admin_auth_failed", reason="invalid_admin_id", admin_id=admin_id_str)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get admin user from database
        result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
        admin_user = result.scalar_one_or_none()

        if admin_user is None:
            logger.warning("admin_auth_failed", reason="admin_not_found", admin_id=admin_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if admin user is active
        if admin_user.status != 1:  # Assuming 1 = active
            logger.warning("admin_auth_failed", reason="admin_inactive", admin_id=admin_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.debug("admin_auth_success", admin_id=admin_id, username=admin_user.username)
        return admin_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("admin_auth_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin_permission(permission: str):
    """
    Dependency factory for requiring specific admin permissions.

    Args:
        permission: The required permission string

    Returns:
        Dependency function that checks the permission
    """

    async def permission_checker(admin_user: AdminUser = Depends(get_current_admin_user)) -> AdminUser:
        """Check if admin user has the required permission."""
        if not admin_user.has_permission(permission):
            logger.warning(
                "admin_permission_denied",
                admin_id=admin_user.id,
                username=admin_user.username,
                required_permission=permission,
                user_role=admin_user.role,
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return admin_user

    return permission_checker
