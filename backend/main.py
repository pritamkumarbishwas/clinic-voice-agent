import asyncio
import contextlib
import json
import math
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from livekit import api

from app.config import sanitize_run_id, settings
from app.database import (
    appointments,
    benchmark_runs,
    call_turns,
    calls,
    client,
    close_database,
    initialize_database,
)
from app.services.latency_report import LATENCY_FIELDS, build_report
from app.workers.analysis_worker import run_worker

load_dotenv()

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_database()

    worker_task = None
    if settings.analysis_worker_enabled:
        worker_task = asyncio.create_task(
            run_worker(), name="analysis-worker"
        )

    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker_task
        await close_database()


app = FastAPI(title="Clinic Voice Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
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
async def generate_token(
    run_id: str | None = Query(None, max_length=48),
):
    livekit_url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

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


@app.get("/api/calls")
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    run_id: str | None = Query(None, max_length=48),
    outcome: str | None = Query(None, max_length=32),
    sentiment: str | None = Query(None, max_length=32),
):
    skip = (page - 1) * page_size
    query: dict = {}

    if run_id:
        query["run_id"] = run_id
    if outcome:
        query["booking_outcome"] = outcome
    if sentiment:
        query["sentiment"] = sentiment

    results = (
        await calls.find(
            query,
            {
                "_id": 0,
                "transcript": 0,
                "tool_calls": 0,
                "agent_config": 0,
            },
        )
        .sort("started_at", -1)
        .skip(skip)
        .limit(page_size)
        .to_list(length=page_size)
    )
    total = await calls.count_documents(query)

    return {
        "items": results,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 1,
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
        {"_id": 0, "slot_id": 0, "doctor_id": 0},
    )

    return {
        "call": call,
        "turn_metrics": turns,
        "appointment": appointment,
    }


@app.post("/api/calls/{call_id}/analyze")
async def requeue_analysis(call_id: str):
    result = await calls.update_one(
        {"call_id": call_id},
        {
            "$set": {
                "analysis_status": "pending",
                "analysis_attempts": 0,
                "analysis_error": None,
                "analysis_locked_at": None,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Call not found")

    return {
        "ok": True,
        "call_id": call_id,
        "analysis_status": "pending",
    }


@app.get("/api/analytics/runs")
async def list_runs():
    pipeline = [
        {"$match": {"run_id": {"$type": "string", "$ne": ""}}},
        {
            "$group": {
                "_id": "$run_id",
                "call_count": {"$sum": 1},
                "first_started_at": {"$min": "$started_at"},
                "last_started_at": {"$max": "$started_at"},
            }
        },
        {"$sort": {"last_started_at": -1}},
        {"$limit": 50},
    ]

    items = await calls.aggregate(pipeline).to_list(length=50)

    return {
        "items": [
            {
                "run_id": item["_id"],
                "call_count": item["call_count"],
                "first_started_at": item.get("first_started_at"),
                "last_started_at": item.get("last_started_at"),
            }
            for item in items
        ]
    }


@app.get("/api/analytics/latency")
async def latency_report(
    run_id: str | None = Query(None, max_length=48),
):
    turn_query: dict = {}
    call_query: dict = {}

    if run_id:
        turn_query["run_id"] = run_id
        call_query["run_id"] = run_id

    projection = {
        field: 1 for field in LATENCY_FIELDS
    } | {"_id": 0, "call_id": 1, "run_id": 1}

    turns = await call_turns.find(turn_query, projection).to_list(
        length=10000
    )
    call_docs = await calls.find(
        call_query,
        {
            "_id": 0,
            "call_id": 1,
            "booking_outcome": 1,
            "barge_in_count": 1,
        },
    ).to_list(length=10000)

    report = build_report(turns, call_docs)
    report["run_id"] = run_id
    return report
