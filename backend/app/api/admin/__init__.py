"""
Admin API router integration.
Combines all admin API endpoints for management backend.
"""

from fastapi import APIRouter

from .dashboard import dashboard_router
from .ai_management import ai_router
from .llm_management import llm_router

# Create main admin API router
admin_api_router = APIRouter()

# Include all admin API routers
admin_api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Admin Dashboard"])
admin_api_router.include_router(ai_router, prefix="/ai", tags=["Admin AI Management"])
admin_api_router.include_router(llm_router, prefix="/llm", tags=["Admin LLM Management"])
