"""FastAPI application factory and bootstrap configuration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.admin import get_admin
from app.api.admin import admin_api_router
from app.api.v1 import v1_router
from app.core.config import Settings, get_settings
from app.core.database import close_database, get_sessionmaker, init_database
from app.middleware.rate_limit import APIRateLimitMiddleware
from app.services.contact.request_worker import start_contact_request_worker
from app.services.message.processing import reset_open_conversation_windows
from app.services.message.processing.scanner import start_buffer_scanner, stop_buffer_scanner
from app.services.message.providers.leancloud import create_leancloud_provider
from app.services.system_config import get_config
from app.utils.logging import configure_logging, get_logger
from app.utils.snowflake import init_snowflake

logger = get_logger(__name__)

api_router = APIRouter()


class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """Trust proxy-provided scheme information."""

    async def dispatch(self, request: Request, call_next):
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        if forwarded_proto:
            request.scope["scheme"] = forwarded_proto
        return await call_next(request)


@api_router.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Health check endpoint that validates DB connectivity."""

    settings = get_settings()
    session_factory = get_sessionmaker()
    try:
        async with session_factory() as db:
            await db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception as exc:  # pragma: no cover - health probe logging only
        logger.error("health_check_database_error", error=str(exc))
        database_status = "error"

    payload = {
        "status": "healthy" if database_status == "connected" else "unhealthy",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": database_status,
    }
    logger.debug("health_check", **payload)
    return JSONResponse(payload)


@api_router.get("/")
async def root() -> JSONResponse:
    """Root endpoint with simple greeting."""

    settings = get_settings()
    return JSONResponse(
        {
            "message": "Hello World!",
            "version": settings.VERSION,
            "docs": "/docs" if settings.DEBUG else None,
        }
    )


@api_router.get("/qiao-dash/theme/{mode}")
async def set_theme(mode: str, request: Request) -> RedirectResponse:
    """Persist admin theme preference via cookie."""

    normalized = mode.lower()
    if normalized not in {"light", "dark", "auto"}:
        normalized = "light"
    referer = request.headers.get("referer")
    fallback = "/qiao-dash/"
    target = referer if referer and referer.startswith(("http://", "https://")) else fallback
    response = RedirectResponse(url=target, status_code=303)
    response.set_cookie(
        "qiao_admin_theme", normalized, max_age=60 * 60 * 24 * 365, path="/", samesite="lax"
    )
    return response


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler to hide internal details."""

    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def _create_lifespan(settings: Settings):
    session_factory = get_sessionmaker()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "starting_application", app_name=settings.PROJECT_NAME, version=settings.VERSION
        )
        try:
            logger.info("initializing_snowflake_generator")
            init_snowflake(settings.SNOWFLAKE_DATACENTER_ID, settings.SNOWFLAKE_MACHINE_ID)
            logger.info("snowflake_generator_initialized")

            logger.info("initializing_database")
            await init_database()
            logger.info("database_initialized")

            async with session_factory() as db:
                await reset_open_conversation_windows(db)

            logger.info("loading_rate_limit_config")
            async with session_factory() as db:
                api_requests = int(await get_config(db, key="api_rate_limit_requests"))
                api_window_seconds = int(await get_config(db, key="api_rate_limit_window_seconds"))
            app.state.api_rate_limit_requests = api_requests
            app.state.api_rate_limit_window_seconds = api_window_seconds
            logger.info(
                "rate_limit_config_loaded",
                api_requests=api_requests,
                api_window_seconds=api_window_seconds,
            )

            logger.info("initializing_message_service")
            try:
                async with session_factory() as db:
                    provider = create_leancloud_provider(db)
                    success = await provider.initialize_service()
                    if success:
                        logger.info("message_service_initialized")
                    else:
                        logger.warning("message_service_initialization_failed")
            except Exception as exc:  # pragma: no cover - logging only
                logger.error("message_service_initialization_error", error=str(exc), exc_info=True)

            try:
                start_contact_request_worker(app)
            except Exception as exc:  # pragma: no cover - logging only
                logger.error("contact_request_worker_start_failed", error=str(exc), exc_info=True)

            await start_buffer_scanner()

            logger.info("application_startup_complete")
            yield

        except Exception as exc:  # pragma: no cover - startup failure
            logger.critical("application_startup_failed", error=str(exc), exc_info=True)
            raise
        finally:
            logger.info("shutting_down_application")
            try:
                await stop_buffer_scanner()
                worker = getattr(app.state, "contact_request_worker", None)
                if worker:
                    worker.cancel()
                await close_database()
                logger.info("application_shutdown_complete")
            except Exception as exc:  # pragma: no cover - logging only
                logger.error("shutdown_error", error=str(exc), exc_info=True)

    return lifespan


def _configure_middlewares(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(ProxyHeadersMiddleware)
    app.add_middleware(APIRateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
    app.add_middleware(SessionMiddleware, secret_key=settings.ADMIN_SECRET_KEY, max_age=86400)


def _register_debug_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def debug_api_requests(request: Request, call_next):  # type: ignore[unused-ignore]
        if "/api/" in str(request.url):
            logger.info(
                "api_request_debug",
                url=str(request.url),
                path=request.url.path,
                path_params=dict(request.path_params),
            )
        return await call_next(request)


def _mount_admin(app: FastAPI) -> None:
    admin_app = get_admin()
    logger.info(
        "mounting_admin_interface", admin_title=admin_app.title, admin_base_url=admin_app.base_url
    )
    logger.info("admin_models_before_mount", models=[model.identity for model in admin_app._models])
    logger.info(
        "admin_models_detailed",
        models=[
            (model.identity, type(model).__name__, getattr(model, "model", None))
            for model in admin_app._models
        ],
    )
    admin_app.mount_to(app)
    logger.info("admin_interface_mounted")
    logger.info("admin_models_after_mount", models=[model.identity for model in admin_app._models])


def create_app() -> FastAPI:
    """Application factory used by ASGI servers."""

    settings = get_settings()
    configure_logging(
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
        log_dir=settings.LOG_DIR,
        service_name="backend",
    )
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Hello World",
        version=settings.VERSION,
        lifespan=_create_lifespan(settings),
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        redirect_slashes=False,
    )
    app.state.settings = settings
    _configure_middlewares(app, settings)
    app.add_exception_handler(Exception, global_exception_handler)
    app.include_router(api_router)
    app.include_router(v1_router, prefix="/api/v1")
    app.include_router(admin_api_router, prefix="/admin-api")
    _mount_admin(app)
    _register_debug_middleware(app)
    logger.info("app_routes", routes=[str(route) for route in app.routes])
    return app


if __name__ == "__main__":
    uvicorn.run(
        "main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=get_settings().DEBUG,
        log_level=get_settings().LOG_LEVEL.lower(),
    )
