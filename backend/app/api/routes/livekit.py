import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from livekit import api

from app.api.deps import limiter
from app.auth import get_optional_user
from app.config import sanitize_run_id, settings
from app.db.mongo import benchmark_runs

router = APIRouter(tags=["livekit"])


@router.get("/generate-token")
@limiter.limit("20/minute")
async def generate_token(
    request: Request,
    run_id: str | None = Query(None, max_length=48),
):
    livekit_url = settings.livekit_url
    api_key = settings.livekit_api_key
    api_secret = settings.livekit_api_secret

    if not all([livekit_url, api_key, api_secret]):
        raise HTTPException(
            status_code=500,
            detail="LiveKit environment variables are missing",
        )

    clean_run_id = None
    if run_id is not None:
        clean_run_id = sanitize_run_id(run_id)
        if clean_run_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "run_id must be 1-48 characters using letters, "
                    "numbers, spaces, hyphens or underscores"
                ),
            )

        user = await get_optional_user(request)
        if user is None or not user.is_admin:
            raise HTTPException(
                status_code=401,
                detail=(
                    "Admin login is required to tag a benchmark run. "
                    "Start a normal call without a run id."
                ),
            )

        await benchmark_runs.update_one(
            {"run_id": clean_run_id},
            {
                "$setOnInsert": {
                    "run_id": clean_run_id,
                    "label": clean_run_id,
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    room_name = f"clinic-{uuid4().hex[:10]}"
    identity = f"patient-{uuid4().hex[:10]}"
    dispatch_metadata = (
        json.dumps({"run_id": clean_run_id}) if clean_run_id else ""
    )

    token_builder = (
        api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_ttl(timedelta(minutes=15))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                can_publish_sources=["microphone"],
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name=settings.livekit_agent_name,
                        metadata=dispatch_metadata,
                    )
                ]
            )
        )
    )

    if clean_run_id:
        token_builder = token_builder.with_metadata(
            json.dumps({"run_id": clean_run_id})
        )

    token = token_builder.to_jwt()

    return {
        "serverUrl": livekit_url,
        "token": token,
        "roomName": room_name,
        "identity": identity,
        "runId": clean_run_id,
    }
