from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from app.config import settings

MONGODB_URI = settings.mongodb_uri
DATABASE_NAME = settings.mongodb_database

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is missing from .env")

client = AsyncIOMotorClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
    tz_aware=True,
    appname="clinic-voice-agent",
)

db = client[DATABASE_NAME]

users = db["users"]
clinic = db["clinic"]
doctors = db["doctors"]
clinic_knowledge = db["clinic_knowledge"]
slots = db["slots"]
appointments = db["appointments"]
calls = db["calls"]
call_turns = db["call_turns"]
benchmark_runs = db["benchmark_runs"]


async def initialize_database() -> None:
    """Verify connectivity once, then make the collection indexes idempotent."""
    await client.admin.command("ping")

    await users.create_index([("email", ASCENDING)], unique=True)
    await users.create_index([("role", ASCENDING), ("active", ASCENDING)])

    await doctors.create_index([("name", ASCENDING)])
    await doctors.create_index([("active", ASCENDING), ("name", ASCENDING)])

    await clinic_knowledge.create_index([("active", ASCENDING)])
    await clinic_knowledge.create_index(
        [("category", ASCENDING), ("active", ASCENDING)]
    )
    await clinic_knowledge.create_index([("updated_at", DESCENDING)])

    await slots.create_index([("doctor_id", ASCENDING), ("start_at", ASCENDING)])
    await slots.create_index([("status", ASCENDING), ("start_at", ASCENDING)])

    await appointments.create_index([("slot_id", ASCENDING)], unique=True)
    await appointments.create_index([("call_id", ASCENDING)])
    await appointments.create_index([("created_at", DESCENDING)])
    await appointments.create_index([("start_at", ASCENDING)])
    await appointments.create_index([("status", ASCENDING), ("start_at", ASCENDING)])
    await appointments.create_index([("doctor_name", ASCENDING)])

    await calls.create_index([("call_id", ASCENDING)], unique=True)
    await calls.create_index([("started_at", DESCENDING)])
    await calls.create_index([("analysis_status", ASCENDING)])
    await calls.create_index([("run_id", ASCENDING), ("started_at", DESCENDING)])

    await call_turns.create_index(
        [("call_id", ASCENDING), ("started_at", ASCENDING)]
    )
    await call_turns.create_index([("call_id", ASCENDING), ("turn_id", ASCENDING)])
    await call_turns.create_index([("started_at", DESCENDING)])
    await call_turns.create_index([("run_id", ASCENDING), ("started_at", DESCENDING)])

    await benchmark_runs.create_index([("run_id", ASCENDING)], unique=True)
    await benchmark_runs.create_index([("created_at", DESCENDING)])


async def close_database() -> None:
    client.close()
