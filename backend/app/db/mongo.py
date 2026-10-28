import logging

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

logger = logging.getLogger("clinic-database")

MONGODB_URI = settings.mongodb_uri
DATABASE_NAME = settings.mongodb_database

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is missing from .env")

client = AsyncIOMotorClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=settings.database_timeout_ms,
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


async def database_ready() -> bool:
    try:
        await client.admin.command("ping")
        return True
    except Exception:
        logger.exception("MongoDB readiness check failed")
        return False


async def initialize_database() -> None:
    """Verify connectivity once, then make the collection indexes idempotent."""
    await client.admin.command("ping")
    from app.db.indexes import create_indexes

    await create_indexes()


async def close_database() -> None:
    client.close()
