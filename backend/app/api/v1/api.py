"""
API v1 router aggregator for the application.
Centralizes all endpoint routing from auth, users, contacts, and messaging services.
"""

from fastapi import APIRouter

from . import auth, users, contacts, message

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
api_router.include_router(message.router, prefix="/message", tags=["message"])
