from fastapi import APIRouter, Body, Request

from app.api.deps import limiter
from app.schemas.voice import VoiceSessionRequest, VoiceSessionResponse
from app.services.voice_session_service import create_voice_session

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post(
    "/session",
    response_model=VoiceSessionResponse,
)
@limiter.limit("20/minute")
async def create_voice_session_endpoint(
    request: Request,
    payload: VoiceSessionRequest | None = Body(default=None),
):
    run_id = payload.run_id if payload else None
    return await create_voice_session(run_id, request)
