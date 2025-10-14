"""
API dependencies for authentication and authorization.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from core.database import get_db
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


# TODO: Add user authentication dependencies when user API is implemented
# async def get_current_user(...)
# async def get_current_active_user(...)
