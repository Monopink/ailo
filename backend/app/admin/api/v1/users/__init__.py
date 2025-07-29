from fastapi import APIRouter

from .users import router

users_router = APIRouter()
users_router.include_router(router, tags=["Admin Users"])

__all__ = ["users_router"]
