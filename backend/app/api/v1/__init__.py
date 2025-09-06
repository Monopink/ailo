"""
API v1 router integration.
Combines all v1 API endpoints.
"""

from fastapi import APIRouter

# Create main v1 router
v1_router = APIRouter()

# TODO: Add other API routes when implemented
# v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
# v1_router.include_router(users_router, prefix="/users", tags=["Users"])
# v1_router.include_router(contacts_router, prefix="/contacts", tags=["Contacts"])
# v1_router.include_router(webhook_router, prefix="/webhook", tags=["Webhook"])
