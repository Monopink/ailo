"""API v1 router integration.
Combines all v1 API endpoints.
"""

from fastapi import APIRouter

from app.api.v1.account_security import router as account_security_router
from app.api.v1.auth import router as auth_router
from app.api.v1.contact_requests import router as contact_requests_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.leancloud import router as leancloud_router
from app.api.v1.media import router as media_router
from app.api.v1.messages import router as messages_router
from app.api.v1.pages import router as pages_router
from app.api.v1.users import router as users_router
from app.api.v1.webhook import router as webhook_router

# Create main v1 router
v1_router = APIRouter()

# Register API routers
v1_router.include_router(auth_router)
v1_router.include_router(webhook_router)
v1_router.include_router(contacts_router)
v1_router.include_router(
    contact_requests_router, prefix="/contact-requests", tags=["Contact Requests"]
)
v1_router.include_router(users_router)
v1_router.include_router(account_security_router)
v1_router.include_router(discovery_router)
v1_router.include_router(pages_router)
v1_router.include_router(leancloud_router)
v1_router.include_router(media_router)
v1_router.include_router(messages_router)
