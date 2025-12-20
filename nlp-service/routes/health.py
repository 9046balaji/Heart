from fastapi import APIRouter, status
from datetime import datetime

router = APIRouter(prefix="/api")


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Basic health check endpoint.
    Returns 200 OK if the service is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "nlp-service",
    }
