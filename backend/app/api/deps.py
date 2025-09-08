"""
API dependencies for authentication and authorization.

This module will contain user authentication dependencies when user API is implemented.
Admin authentication is handled by Starlette-Admin session-based authentication.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from utils.logging import get_logger

logger = get_logger(__name__)

# TODO: Add user authentication dependencies when user API is implemented
# async def get_current_user(...)
# async def get_current_active_user(...)
