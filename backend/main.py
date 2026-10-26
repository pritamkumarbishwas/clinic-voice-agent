import asyncio
import contextlib
import json
import logging
import math
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.auth import (
    CurrentUser,
    LoginRequest,
    authenticate_user,
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    get_optional_user,
    public_user,
    require_admin,
    set_auth_cookie,
)
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
from app.services.appointment_service import (
    list_appointments as db_list_appointments,
    list_doctors as db_list_doctors,
)
from app.services.clinic_service import (
    ClinicProfile,
    get_clinic_profile,
    update_clinic_profile,
)
from app.services.latency_report import LATENCY_FIELDS, build_report
from app.workers.analysis_worker import run_worker

load_dotenv()

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO)
)
logger = logging.getLogger("clinic-api")

if settings.sentry_dsn:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment,
            traces_sample_rate=0.1,
        )
    except Exception:
        logger.exception("Could not initialise Sentry")

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:4173,http://127.0.0.1:4173"
)


def _rate_limit_key(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_rate_limit_key,
    enabled=settings.rate_limit_enabled,
)


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


async def _database_ready() -> bool:
    try:
        await client.admin.command("ping")
        return True
    except Exception:
        return False


@app.get("/api/health")
async def health_check():
    if not await _database_ready():
        raise HTTPException(status_code=503, detail="Database unavailable")

    return {
        "status": "healthy",
        "service": "clinic-voice-agent",
        "database": "ok",
    }


@app.get("/api/ready")
async def readiness_check():
    return await health_check()


@app.post("/api/auth/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
):
    user = await authenticate_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    token = create_access_token(user)
    set_auth_cookie(response, token)
    return {"user": public_user(user)}


@app.post("/api/auth/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@app.get("/api/auth/me")
async def current_user(user: CurrentUser = Depends(get_current_user)):
    return {"user": public_user(user)}


@app.get("/api/generate-token")
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


@app.get("/api/calls")
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    run_id: str | None = Query(None, max_length=48),
    outcome: str | None = Query(None, max_length=32),
    sentiment: str | None = Query(None, max_length=32),
    _: CurrentUser = Depends(require_admin),
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
async def get_call(
    call_id: str,
    _: CurrentUser = Depends(require_admin),
):
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
async def requeue_analysis(
    call_id: str,
    _: CurrentUser = Depends(require_admin),
):
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


@app.get("/api/appointments")
async def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, max_length=32),
    doctor: str | None = Query(None, max_length=120),
    date: str | None = Query(None, max_length=10),
    _: CurrentUser = Depends(require_admin),
):
    try:
        return await db_list_appointments(
            page=page,
            page_size=page_size,
            status=status,
            doctor=doctor,
            date_value=date,
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="date must use YYYY-MM-DD format",
        )


@app.get("/api/doctors")
async def list_doctors(_: CurrentUser = Depends(require_admin)):
    return {"items": await db_list_doctors()}


@app.get("/api/clinic")
async def read_clinic(_: CurrentUser = Depends(require_admin)):
    return await get_clinic_profile()


@app.put("/api/clinic")
async def write_clinic(
    profile: ClinicProfile,
    _: CurrentUser = Depends(require_admin),
):
    return await update_clinic_profile(profile)


@app.get("/api/analytics/runs")
async def list_runs(_: CurrentUser = Depends(require_admin)):
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
    _: CurrentUser = Depends(require_admin),
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
