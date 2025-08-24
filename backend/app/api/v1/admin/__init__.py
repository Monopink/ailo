"""
Admin API router integration.
Combines all admin-related API endpoints.
"""

from fastapi import APIRouter

from .auth import router as auth_router, auth_router as admin_auth_router
from .users import router as users_router
from .auditlog import router as auditlog_router

# Create main admin router for standard admin operations
admin_router = APIRouter()

# Include all admin sub-routers
admin_router.include_router(auth_router, tags=["Admin Auth"])
admin_router.include_router(users_router, prefix="/users", tags=["Admin Users"])
admin_router.include_router(auditlog_router, prefix="/auditlog", tags=["Admin Audit"])

# Export the obfuscated auth router for security path mapping
__all__ = ["admin_router", "admin_auth_router"]
