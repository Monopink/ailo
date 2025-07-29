"""
Simplified admin API v1 router.
Contains only essential admin routes.
"""

from fastapi import APIRouter

from .base import base_router
from .users import users_router

v1_router = APIRouter()

# Base routes (login, etc.) - no authentication required
v1_router.include_router(base_router, prefix="/base")

# Protected routes - authentication handled by individual endpoints
v1_router.include_router(users_router, prefix="/users")
