import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import Request
from livekit import api

from app.auth import get_optional_user
from app.config import sanitize_run_id, settings
from app.core.errors import ApiError
from app.db.mongo import benchmark_runs


def create_session_token(room_name: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "voice-session",
        "scope": "voice_session",
        "room_name": room_name,
        "iat": now,
        "exp": now
        + timedelta(minutes=settings.voice_session_ttl_minutes),
        "jti": uuid4().hex,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_session_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:
        raise ApiError(
            status_code=401,
            code="INVALID_SESSION_TOKEN",
            message="Voice session token is invalid or expired.",
        ) from exc

    if (
        payload.get("scope") != "voice_session"
        or not payload.get("room_name")
    ):
        raise ApiError(
            status_code=401,
            code="INVALID_SESSION_TOKEN",
            message="Voice session token is invalid or expired.",
        )
    return payload


async def create_livekit_token(
    run_id: str | None,
    request: Request,
) -> dict:
    livekit_url = settings.livekit_url
    api_key = settings.livekit_api_key
    api_secret = settings.livekit_api_secret

    if not all([livekit_url, api_key, api_secret]):
        raise ApiError(
            status_code=503,
            code="VOICE_UNAVAILABLE",
            message="Voice service is not configured.",
        )

    clean_run_id = None
    if run_id is not None:
        clean_run_id = sanitize_run_id(run_id)
        if clean_run_id is None:
            raise ApiError(
                status_code=422,
                code="INVALID_RUN_ID",
                message=(
                    "run_id must be 1-48 characters using letters, "
                    "numbers, spaces, hyphens or underscores."
                ),
            )

        user = await get_optional_user(request)
        if user is None or not user.is_admin:
            raise ApiError(
                status_code=401,
                code="ADMIN_REQUIRED",
                message="Admin login is required to tag a benchmark run.",
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
        .with_ttl(
            timedelta(minutes=settings.voice_session_ttl_minutes)
        )
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

    return {
        "serverUrl": livekit_url,
        "token": token_builder.to_jwt(),
        "roomName": room_name,
        "identity": identity,
        "runId": clean_run_id,
    }


async def create_voice_session(
    run_id: str | None,
    request: Request,
) -> dict:
    token_data = await create_livekit_token(run_id, request)
    return {
        "server_url": token_data["serverUrl"],
        "token": token_data["token"],
        "room_name": token_data["roomName"],
        "identity": token_data["identity"],
        "run_id": token_data["runId"],
        "session_token": create_session_token(token_data["roomName"]),
        "expires_in": settings.voice_session_ttl_minutes * 60,
    }
