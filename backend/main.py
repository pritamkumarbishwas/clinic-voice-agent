import math
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from livekit import api

from app.database import (
    appointments,
    call_turns,
    calls,
    client,
    close_database,
    initialize_database,
)

load_dotenv()

LATENCY_FIELDS = (
    "endpoint_latency_ms",
    "stt_latency_ms",
    "llm_latency_ms",
    "tts_latency_ms",
    "end_to_audio_ms",
)

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_database()
    yield
    await close_database()


app = FastAPI(title="Clinic Voice Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    try:
        await client.admin.command("ping")
        database = "ok"
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")

    return {
        "status": "healthy",
        "service": "clinic-voice-agent",
        "database": database,
    }


@app.get("/api/generate-token")
async def generate_token():
    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([livekit_url, api_key, api_secret]):
        raise HTTPException(
            status_code=500,
            detail="LiveKit environment variables are missing",
        )

    room_name = f"clinic-{uuid4().hex[:10]}"
    identity = f"patient-{uuid4().hex[:10]}"

    token = (
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
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name=os.getenv(
                            "LIVEKIT_AGENT_NAME",
                            "clinic-receptionist",
                        )
                    )
                ]
            )
        )
        .to_jwt()
    )

    return {
        "serverUrl": livekit_url,
        "token": token,
        "roomName": room_name,
        "identity": identity,
    }


@app.get("/api/calls")
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    skip = (page - 1) * page_size

    results = (
        await calls.find({}, {"_id": 0})
        .sort("started_at", -1)
        .skip(skip)
        .limit(page_size)
        .to_list(length=page_size)
    )
    total = await calls.count_documents({})

    return {
        "items": results,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size),
    }


@app.get("/api/calls/{call_id}")
async def get_call(call_id: str):
    call = await calls.find_one({"call_id": call_id}, {"_id": 0})
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    turns = (
        await call_turns.find({"call_id": call_id}, {"_id": 0})
        .sort("started_at", 1)
        .to_list(length=500)
    )
    appointment = await appointments.find_one(
        {"call_id": call_id},
        {"_id": 0},
    )

    return {
        "call": call,
        "turn_metrics": turns,
        "appointment": appointment,
    }


@app.get("/api/analytics/latency")
async def latency_report():
    projection = {field: 1 for field in LATENCY_FIELDS} | {"_id": 0}

    turns = await call_turns.find({}, projection).to_list(length=10000)

    report = {}

    for field in LATENCY_FIELDS:
        values = sorted(
            row[field]
            for row in turns
            if isinstance(row.get(field), (int, float))
            and math.isfinite(row[field])
            and row[field] >= 0
        )

        if not values:
            report[field] = {
                "count": 0,
                "p50_ms": None,
                "p95_ms": None,
            }
            continue

        def percentile(p: float) -> float:
            index = max(0, math.ceil(p * len(values)) - 1)
            return round(values[index], 2)

        report[field] = {
            "count": len(values),
            "p50_ms": percentile(0.50),
            "p95_ms": percentile(0.95),
        }

    return {"metrics": report}
