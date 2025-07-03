from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.utils.logging import get_logger, configure_logging

# Create FastAPI application
app = FastAPI(title=settings.PROJECT_NAME)

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Specific origins for credentials
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """
    Application startup logic.
    """
    logger.info("starting_accounts_service", project_name=settings.PROJECT_NAME)


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown logic.
    """
    logger.info("shutting_down_accounts_service")


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    """
    logger.debug("health_check_requested")
    return {"status": "ok", "service": settings.PROJECT_NAME}


app.include_router(api_router, prefix="/api/v1")
