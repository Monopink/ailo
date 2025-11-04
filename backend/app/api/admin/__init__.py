"""
Admin API router integration.
Combines all admin API endpoints for management backend.

All admin API endpoints require authentication via Starlette-Admin session.
"""

from fastapi import APIRouter, Depends

from api.deps import verify_admin_session

from .dashboard import dashboard_router
from .llm_management import llm_router
from .ai_character import character_router
from .ai_personality import personality_router
from .ai_template import template_router
from .ai_style import style_router
from .ai_dimension import dimension_router
from .system_management import system_router

# Create main admin API router with global authentication
admin_api_router = APIRouter(dependencies=[Depends(verify_admin_session)])

# Include all admin API routers
admin_api_router.include_router(dashboard_router, prefix="/dashboard", tags=["Admin Dashboard"])
admin_api_router.include_router(llm_router, prefix="/llm", tags=["Admin LLM Management"])
admin_api_router.include_router(character_router, prefix="/ai", tags=["Admin AI Character"])
admin_api_router.include_router(personality_router, prefix="/ai", tags=["Admin AI Personality"])
admin_api_router.include_router(template_router, prefix="/ai", tags=["Admin AI Template"])
admin_api_router.include_router(style_router, prefix="/ai", tags=["Admin AI Style"])
admin_api_router.include_router(dimension_router, prefix="/ai", tags=["Admin AI Dimension"])
admin_api_router.include_router(system_router, prefix="/system", tags=["Admin System Management"])
