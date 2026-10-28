from fastapi import APIRouter, HTTPException

from app.db.mongo import database_ready
from app.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health/live",
    response_model=LivenessResponse,
)
async def liveness_check():
    return {
        "status": "alive",
        "service": "clinic-voice-agent",
    }


@router.get(
    "/health",
    response_model=ReadinessResponse,
)
async def health_check():
    if not await database_ready():
        raise HTTPException(status_code=503, detail="Database unavailable")

    return {
        "status": "healthy",
        "service": "clinic-voice-agent",
        "database": "ok",
    }


@router.get(
    "/ready",
    response_model=ReadinessResponse,
)
async def readiness_check():
    return await health_check()
