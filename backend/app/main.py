from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from core.config import settings
from core.database import SessionLocal, init_database
from core.event_bus import event_bus
from services.message import websocket
from services.ai_chat.model_router import model_router
from exceptions import AppException
from utils.logging import get_logger, bind_context, configure_logging
from services.message.providers.leancloud import setup_leancloud_handlers
from api.v1.api import api_router
from admin.main import admin_router


logger = get_logger(__name__)

# Create FastAPI application
app = FastAPI(title=settings.PROJECT_NAME)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",  # Frontend
        "http://localhost:8000",  # Admin interface
        "http://127.0.0.1:8000",  # Admin interface
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Include admin router
app.include_router(admin_router, prefix="/admin")


async def app_exception_handler(request: Request, exc: AppException):
    logger.error("application_exception", status_code=exc.status_code, detail=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.on_event("startup")
async def startup_event():
    """
    Initialize application on startup
    """
    # Configure logging first to ensure all subsequent logs are structured.
    configure_logging()
    try:
        logger.info("starting_application")

        # Initialize database connection
        logger.info("initializing_database")
        await init_database()
        logger.info("database_initialized")

        # Start event bus
        logger.info("starting_event_bus")
        await event_bus.start()
        logger.info("event_bus_started")

        # Ensure model_router is created and subscribed to events
        logger.info("initializing_model_router")
        if not hasattr(app.state, "model_router"):
            app.state.model_router = model_router
        logger.info("model_router_initialized")

        # Initialize WebSocket manager
        logger.info("initializing_websocket_manager")
        if not hasattr(app.state, "websocket_manager"):
            app.state.websocket_manager = websocket
            active_connections = len(websocket.active_connections)
            logger.info("websocket_connections", count=active_connections)
        logger.info("websocket_manager_initialized")

        # Perform LeanCloud message service startup check
        logger.info("performing_leancloud_message_service_startup_check")
        from services.message.providers.leancloud.startup import startup_leancloud_message_service_check

        startup_success = await startup_leancloud_message_service_check()
        if not startup_success:
            logger.error("leancloud_message_service_startup_check_failed")
            # Application can choose whether to continue startup
            # For MVP development, we continue but log the failure
        else:
            logger.info("leancloud_message_service_startup_check_passed")

        # Initialize LeanCloud handlers
        logger.info("initializing_leancloud_handlers")
        setup_leancloud_handlers()
        logger.info("leancloud_handlers_initialized")

        logger.info("application_startup_complete")

        # Add the exception handler to the app
        app.add_exception_handler(AppException, app_exception_handler)
    except Exception as e:
        logger.critical("application_startup_failed", error=str(e), exc_info=True)
        import sys

        sys.exit(1)


@app.on_event("shutdown")
async def shutdown_event():
    """
    Clean up resources on application shutdown
    """
    try:
        # Stop event bus
        await event_bus.stop()
        logger.info("event_bus_stopped")

        # Close all WebSocket connections
        for client_id in list(websocket.active_connections.keys()):
            await websocket.disconnect(client_id)
        logger.info("websocket_connections_closed")

        logger.info("application_shutdown_complete")
    except Exception as e:
        logger.error("shutdown_error", error=str(e), exc_info=True)


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(ws: WebSocket, client_id: str):
    """
    WebSocket connection endpoint
    """
    ws_logger = bind_context(logger, client_id=client_id)
    try:
        ws_logger.info("websocket_connection_request")
        await websocket.connect(ws, client_id)
        await websocket.receive_message(ws, client_id)
    except Exception as e:
        ws_logger.error("websocket_error", error=str(e), exc_info=True)
        await websocket.disconnect(client_id)


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint
    """
    # Test database connection
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "error"

    # Get LeanCloud message service health status
    try:
        from services.message.providers.leancloud.health_checker import health_checker

        leancloud_health = await health_checker.check_leancloud_message_service_health()
    except Exception as e:
        logger.error("health_check_leancloud_error", error=str(e))
        leancloud_health = {"leancloud_message_service": "error", "details": {"error": str(e)}}

    status = {
        "status": "healthy",
        "database": database_status,
        "event_bus": "running" if event_bus._running else "stopped",
        "leancloud_message_service": leancloud_health,
    }
    logger.debug("health_check", **status)
    return status


@app.post("/webhook/leanmessage")
async def leanmessage_webhook(request: Request):
    """
    LeanMessage webhook endpoint for receiving messages
    """
    from services.message.providers.leancloud.webhook import handle_leancloud_message_webhook

    return await handle_leancloud_message_webhook(request)
