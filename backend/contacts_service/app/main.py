from fastapi import FastAPI
from .core.config import settings
from .routers import contacts
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Create FastAPI application
app = FastAPI(title=settings.PROJECT_NAME)

# Include routers with API version prefix
app.include_router(contacts.router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """
    Application startup logic.
    """
    print("Starting up Contacts Service...")
    print(f"Connecting to database at: {settings.database_url}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown logic.
    """
    print("Shutting down Contacts Service.")


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok"}
