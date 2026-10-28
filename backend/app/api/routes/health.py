from fastapi import APIRouter, HTTPException

from app.db.mongo import database_ready

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness_check():
    return {
        "status": "alive",
        "service": "clinic-voice-agent",
    }


@router.get("/health")
async def health_check():
    if not await database_ready():
        raise HTTPException(status_code=503, detail="Database unavailable")

    return {
        "status": "healthy",
        "service": "clinic-voice-agent",
        "database": "ok",
    }


@router.get("/ready")
async def readiness_check():
    return await health_check()
