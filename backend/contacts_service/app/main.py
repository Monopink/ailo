from fastapi import FastAPI
from .core.config import settings
from .routers import contacts
from .middleware import RateLimitMiddleware
from .utils.logging import get_logger, configure_logging

# Configure structured logging
configure_logging()

logger = get_logger(__name__)

# Create FastAPI application
app = FastAPI(title=settings.PROJECT_NAME)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Include routers with API version prefix
app.include_router(contacts.router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """
    Application startup logic.
    """
    logger.info(
        "contacts_service_starting", service_name=settings.PROJECT_NAME, database_url=settings.database_url
    )


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown logic.
    """
    logger.info("contacts_service_shutting_down", service_name=settings.PROJECT_NAME)


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok"}
