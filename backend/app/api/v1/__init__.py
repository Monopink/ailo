"""
API v1 router integration.
Combines all v1 API endpoints.
"""

from fastapi import APIRouter

from .admin import admin_router, admin_auth_router

# Create main v1 router
v1_router = APIRouter()

# Admin authentication with obfuscated path for security
# Note: "abandoned" is used as a security measure to hide the admin login endpoint
# from potential attackers. The actual functionality is admin authentication.
v1_router.include_router(admin_auth_router, prefix="/abandoned", tags=["Admin Auth"])

# Include admin routes
v1_router.include_router(admin_router, prefix="/admin", tags=["Admin"])

# TODO: Add other API routes when implemented
# v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
# v1_router.include_router(users_router, prefix="/users", tags=["Users"])
# v1_router.include_router(contacts_router, prefix="/contacts", tags=["Contacts"])
# v1_router.include_router(webhook_router, prefix="/webhook", tags=["Webhook"])
