"""WebSocket API routers."""

from fastapi import APIRouter

from .messages import router as messages_router

ws_router = APIRouter()
ws_router.include_router(messages_router)

__all__ = ["ws_router"]
