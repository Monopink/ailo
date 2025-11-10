from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text

from core.config import settings
from core.database import SessionLocal, init_database, close_database
from utils.logging import configure_logging, get_logger
from utils.snowflake import init_snowflake
from api.v1 import v1_router
from api.admin import admin_api_router
from admin import admin
from middleware.rate_limit import APIRateLimitMiddleware

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
        # Initialize Snowflake ID generator
        logger.info("initializing_snowflake_generator")
        init_snowflake(
            datacenter_id=settings.SNOWFLAKE_DATACENTER_ID, machine_id=settings.SNOWFLAKE_MACHINE_ID
        )
        logger.info("snowflake_generator_initialized")

        # Initialize database connection
        logger.info("initializing_database")
        await init_database()
        logger.info("database_initialized")

        # Load rate limit configuration for middleware
        logger.info("loading_rate_limit_config")
        from services.system_config import get_config

        async with SessionLocal() as db:
            api_requests = int(await get_config(db, key="api_rate_limit_requests"))
            api_window = int(await get_config(db, key="api_rate_limit_window"))

        app.state.api_rate_limit_requests = api_requests
        app.state.api_rate_limit_window = api_window

        logger.info("rate_limit_config_loaded", api_requests=api_requests, api_window=api_window)

        # Initialize message service (LeanCloud)
        logger.info("initializing_message_service")
        try:
            from services.message.providers.leancloud import create_leancloud_provider

            async with SessionLocal() as db:
                provider = create_leancloud_provider(db)
                success = await provider.initialize_service()
                if success:
                    logger.info("message_service_initialized")
                else:
                    logger.warning("message_service_initialization_failed")
        except Exception as e:
            logger.error("message_service_initialization_error", error=str(e), exc_info=True)

        # Start background worker for contact requests (MVP)
        try:
            from services.contact.request_worker import start_contact_request_worker

            start_contact_request_worker(app)
        except Exception as e:
            logger.error("contact_request_worker_start_failed", error=str(e), exc_info=True)

        logger.info("application_startup_complete")
        yield

    except Exception as e:
        logger.critical("application_startup_failed", error=str(e), exc_info=True)
        raise

    # Shutdown
    logger.info("shutting_down_application")
    try:
        # Stop background worker if running
        worker = getattr(app.state, "contact_request_worker", None)
        if worker:
            worker.cancel()
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
    redirect_slashes=False,  # Disable automatic slash redirects
)


# Proxy headers middleware - must be first to handle X-Forwarded-* headers
class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to trust X-Forwarded-* headers from reverse proxy.
    This ensures request.url.scheme reflects the actual protocol (https) used by clients.
    """

    async def dispatch(self, request: Request, call_next):
        # Trust X-Forwarded-Proto header from Nginx
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        if forwarded_proto:
            # Modify the request scope to use the forwarded protocol
            request.scope["scheme"] = forwarded_proto

        response = await call_next(request)
        return response


app.add_middleware(ProxyHeadersMiddleware)

# API rate limit middleware (must be before other middlewares to protect early)
app.add_middleware(APIRateLimitMiddleware)

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

# Session middleware for admin authentication
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.ADMIN_SECRET_KEY,
    max_age=86400,  # 24 hours
)



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
app.include_router(admin_api_router, prefix="/admin-api")

# Mount admin interface
logger.info("mounting_admin_interface", admin_title=admin.title, admin_base_url=admin.base_url)

# Debug: Print admin models before mounting
logger.info("admin_models_before_mount", models=[model.identity for model in admin._models])
logger.info(
    "admin_models_detailed",
    models=[
        (model.identity, type(model).__name__, getattr(model, "model", None)) for model in admin._models
    ],
)

admin.mount_to(app)
logger.info("admin_interface_mounted")

# Debug: Print admin models after mounting
logger.info("admin_models_after_mount", models=[model.identity for model in admin._models])


# Add debug middleware to log API requests
@app.middleware("http")
async def debug_api_requests(request: Request, call_next):
    if "/api/" in str(request.url):
        logger.info(
            "api_request_debug",
            url=str(request.url),
            path=request.url.path,
            path_params=dict(request.path_params),
        )
    response = await call_next(request)
    return response


# Debug: Print all routes
logger.info("app_routes", routes=[str(route) for route in app.routes])


# Theme switch (SSR): set cookie and redirect back
@app.get("/qiao-dash/theme/{mode}")
async def set_theme(mode: str, request: Request):
    mode = mode.lower()
    if mode not in ("light", "dark", "auto"):
        mode = "light"
    referer = request.headers.get("referer")
    fallback = "/qiao-dash/"
    target = referer if referer and referer.startswith(("http://", "https://")) else fallback
    response = RedirectResponse(url=target, status_code=303)
    # Persist for a year
    response.set_cookie("qiao_admin_theme", mode, max_age=60 * 60 * 24 * 365, path="/", samesite="lax")
    return response


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
