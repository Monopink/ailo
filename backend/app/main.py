from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from .services import websocket
from .event_bus import event_bus
from .database import SessionLocal, init_database
from .message_router import message_router
from .exceptions import AppException
from .utils.logging import get_logger, bind_context, configure_logging
from .core.config import settings
from .services.leanmessage import setup_leanmessage_handlers
from .api.v1.endpoints.system import router as system_router


logger = get_logger(__name__)

# Create FastAPI application
app = FastAPI(title=settings.PROJECT_NAME)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Specific origins for credentials
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include API routers
app.include_router(system_router, prefix="/api/v1/system", tags=["system"])


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

        # Ensure message_router is created and subscribed to events
        logger.info("initializing_message_router")
        if not hasattr(app.state, "message_router"):
            app.state.message_router = message_router
        logger.info("message_router_initialized")

        # Initialize WebSocket manager
        logger.info("initializing_websocket_manager")
        if not hasattr(app.state, "websocket_manager"):
            app.state.websocket_manager = websocket
            active_connections = len(websocket.active_connections)
            logger.info("websocket_connections", count=active_connections)
        logger.info("websocket_manager_initialized")

        # Ensure unified conversation exists
        logger.info("ensuring_unified_conversation")
        from .services.leancloud.conversation_auto_setup import ensure_unified_conversation

        await ensure_unified_conversation()
        logger.info("unified_conversation_ready")

        # Initialize LeanMessage handlers
        logger.info("initializing_leanmessage_handlers")
        setup_leanmessage_handlers()
        logger.info("leanmessage_handlers_initialized")

        # Start LeanCloud health monitoring
        logger.info("starting_leancloud_health_monitoring")
        from .services.leancloud import health_checker

        await health_checker.start_health_monitoring()
        logger.info("leancloud_health_monitoring_started")

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
        # Stop LeanCloud health monitoring
        logger.info("stopping_leancloud_health_monitoring")
        from .services.leancloud import health_checker

        await health_checker.stop_health_monitoring()
        logger.info("leancloud_health_monitoring_stopped")

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


@app.get("/health")
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

    # Get LeanCloud conversation health status and metrics
    from .services.leancloud import health_checker
    from .services.leancloud import conversation_metrics

    leancloud_health = health_checker.get_current_health_status()
    metrics_summary = conversation_metrics.get_metrics_summary()

    status = {
        "status": "healthy",
        "database": database_status,
        "event_bus": "running" if event_bus._running else "stopped",
        "leancloud_conversation": {"health": leancloud_health, "metrics": metrics_summary},
    }
    logger.debug("health_check", **status)
    return status


@app.post("/webhook/leanmessage")
async def leanmessage_webhook(request: Request):
    """
    LeanMessage webhook endpoint for receiving messages
    """
    from .services.leancloud.leanmessage_webhook import handle_leanmessage_webhook

    return await handle_leanmessage_webhook(request)


@app.get("/")
async def root():
    """
    Root path response
    """
    response = {"message": "Welcome to Says API", "version": "1.0.0", "status": "running"}
    logger.info("root_endpoint_accessed")
    return response
