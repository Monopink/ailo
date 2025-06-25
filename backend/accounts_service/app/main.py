from fastapi import FastAPI
from .core.config import settings

# Create FastAPI application
app = FastAPI(title=settings.PROJECT_NAME)


@app.on_event("startup")
async def startup_event():
    """
    Application startup logic.
    """
    print("Starting up Accounts Service...")
    print(f"Connecting to database at: {settings.database_url}")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown logic.
    """
    print("Shutting down Accounts Service.")


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok"}
