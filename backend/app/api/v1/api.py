"""
API v1 router aggregator for the application.
Centralizes all endpoint routing from accounts, contacts, and messaging services.
"""

from fastapi import APIRouter

from .client import auth, users, contacts, messaging

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
api_router.include_router(messaging.router, prefix="/messaging", tags=["messaging"])
