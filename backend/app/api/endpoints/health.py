from fastapi import APIRouter, Response, status
from app.core.config import settings
from app.db.session import check_db_connection

router = APIRouter()

@router.get("/health", tags=["Health"])
async def system_health():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "phase": "Phase 2 - Neon PostgreSQL Integration"
    }

@router.get("/db/health", tags=["Health"])
async def database_health(response: Response):
    """
    Live Neon PostgreSQL database health check endpoint.
    Returns database metadata, active branch, and round-trip query latency.
    """
    db_status = check_db_connection()
    if db_status.get("status") != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return db_status
