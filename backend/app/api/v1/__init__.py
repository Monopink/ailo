"""
API v1 router integration.
Combines all v1 API endpoints.
"""

from api.v1.account_security import router as account_security_router
from api.v1.auth import router as auth_router
from api.v1.contact_requests import router as contact_requests_router
from api.v1.contacts import router as contacts_router
from api.v1.conversation import router as conversation_router
from api.v1.discovery import router as discovery_router
from api.v1.system import router as system_router
from api.v1.users import router as users_router
from api.v1.webhook import router as webhook_router
from fastapi import APIRouter

# Create main v1 router
v1_router = APIRouter()

# Register API routers
v1_router.include_router(auth_router)
v1_router.include_router(webhook_router)
v1_router.include_router(contacts_router)
v1_router.include_router(contact_requests_router, prefix="/contact-requests", tags=["Contact Requests"])
v1_router.include_router(users_router)
v1_router.include_router(account_security_router)
v1_router.include_router(discovery_router)
v1_router.include_router(system_router)
v1_router.include_router(conversation_router)
