from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .services import websocket
from .event_bus import event_bus
from .db_managers import db_manager
from .message_router import message_router
from .exceptions import AppException
from .utils.logging import get_logger, bind_context, configure_logging
from .core.config import settings
from .services.leanmessage import setup_leanmessage_handlers


logger = get_logger(__name__)

# Create FastAPI application
app = FastAPI(title=settings.PROJECT_NAME)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Should specify actual domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


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

        # Start event bus
        logger.info("starting_event_bus")
        await event_bus.start()
        logger.info("event_bus_started")

        # Wait for database initialization
        await db_manager._init_task
        logger.info("database_initialized")

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

        # Initialize LeanMessage handlers
        logger.info("initializing_leanmessage_handlers")
        setup_leanmessage_handlers()
        logger.info("leanmessage_handlers_initialized")

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


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    status = {
        "status": "healthy",
        "database": "connected" if db_manager._init_task.done() else "initializing",
        "event_bus": "running" if event_bus._running else "stopped",
    }
    logger.debug("health_check", **status)
    return status


@app.post("/webhook/leanmessage")
async def leanmessage_webhook(request: Request):
    """
    LeanMessage webhook endpoint for receiving messages
    """
    from .services.leanmessage_webhook import handle_leanmessage_webhook

    return await handle_leanmessage_webhook(request)


@app.get("/")
async def root():
    """
    Root path response
    """
    response = {"message": "Welcome to Says API", "version": "1.0.0", "status": "running"}
    logger.info("root_endpoint_accessed")
    return response
