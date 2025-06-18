import logging
import sys
import uvicorn
import structlog
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from services import websocket
from event_bus import event_bus
from db_managers import db_manager
from message_router import message_router
from exceptions import AppException
from fastapi.responses import JSONResponse
from utils.logging import get_logger, bind_context


# Configure structured logging
def configure_logging():
    # The default basicConfig sets the root logger level to WARNING.
    # We will configure it manually to ensure DEBUG messages are captured.
    # logging.basicConfig(level=logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.CallsiteParameterAdder(),
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Get the root logger
    root_logger = logging.getLogger()
    # Set the root logger level to the lowest level we want to capture (DEBUG)
    root_logger.setLevel(logging.DEBUG)

    # Clear any existing handlers to avoid duplicate logs
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Set up file logging to capture all details (DEBUG and above)
    file_handler = logging.FileHandler("app.log")
    file_handler.setLevel(logging.DEBUG)

    # Set up console logging for DEBUG level as well
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Add the handlers to the root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


configure_logging()
logger = get_logger("says.main")

# Create FastAPI application
app = FastAPI()

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


@app.get("/")
async def root():
    """
    Root path response
    """
    response = {"message": "Welcome to Says API", "version": "1.0.0", "status": "running"}
    logger.info("root_endpoint_accessed")
    return response


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",  # Changed from debug to info for production logs
        ws_ping_interval=20,
        ws_ping_timeout=20,
        access_log=True,
    )
