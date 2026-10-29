from fastapi import APIRouter, Query, Request

from app.api.deps import limiter
from app.services.voice_session_service import create_livekit_token

router = APIRouter(tags=["livekit"])


@router.get("/generate-token")
@limiter.limit("20/minute")
async def generate_token(
    request: Request,
    run_id: str | None = Query(None, max_length=48),
):
    return await create_livekit_token(run_id, request)
