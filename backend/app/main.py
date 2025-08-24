from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy import text

from core.config import settings
from core.database import SessionLocal, init_database, close_database
from utils.logging import configure_logging, get_logger
from api.v1 import v1_router

configure_logging(
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT,
    log_dir=settings.LOG_DIR,
    service_name="backend",
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("starting_application", app_name=settings.PROJECT_NAME, version=settings.VERSION)

    try:
        # Initialize database connection
        logger.info("initializing_database")
        await init_database()
        logger.info("database_initialized")

        logger.info("application_startup_complete")
        yield

    except Exception as e:
        logger.critical("application_startup_failed", error=str(e), exc_info=True)
        raise

    # Shutdown
    logger.info("shutting_down_application")
    try:
        await close_database()
        logger.info("application_shutdown_complete")
    except Exception as e:
        logger.error("shutdown_error", error=str(e), exc_info=True)


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Hello World",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)


# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

# Static files (for media uploads)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    # Directory doesn't exist yet, will be created when needed
    logger.warning("static_directory_not_found", directory="static")


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(
        "unhandled_exception", path=request.url.path, method=request.method, error=str(exc), exc_info=True
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    # Test database connection
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception as e:
        logger.error("health_check_database_error", error=str(e))
        database_status = "error"

    status = {
        "status": "healthy" if database_status == "connected" else "unhealthy",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": database_status,
    }

    logger.debug("health_check", **status)
    return status


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Hello World!",
        "version": settings.VERSION,
        "docs": "/docs" if settings.DEBUG else None,
    }


# Include API routes
app.include_router(v1_router, prefix="/api/v1")

# TODO: Add webhook endpoint when message service implemented


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
