"""
Admin application main entry point.
Integrates admin functionality with the main application.
"""

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from admin.api.v1 import v1_router
from admin.settings import admin_settings
from utils.logging import get_logger

logger = get_logger(__name__)

# Create admin router
admin_router = APIRouter()

# Include API v1 routes
admin_router.include_router(v1_router, prefix="/api/v1")

# Health check endpoint
@admin_router.get("/health")
async def health_check():
    """Admin health check endpoint"""
    return {"status": "ok", "service": "admin"}

# Create admin app (can be mounted to main app)
def create_admin_app() -> FastAPI:
    """
    Create admin FastAPI application.
    Can be used as a standalone app or mounted to main app.
    """
    app = FastAPI(
        title=admin_settings.APP_TITLE,
        description=admin_settings.APP_DESCRIPTION,
        version=admin_settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=admin_settings.CORS_ORIGINS,
        allow_credentials=admin_settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=admin_settings.CORS_ALLOW_METHODS,
        allow_headers=admin_settings.CORS_ALLOW_HEADERS,
    )
    
    # Include admin routes
    app.include_router(admin_router)
    
    @app.on_event("startup")
    async def startup_event():
        logger.info("admin_app_startup", title=admin_settings.APP_TITLE)
    
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("admin_app_shutdown")
    
    return app

# Export the router for mounting to main app
__all__ = ["admin_router", "create_admin_app"]
