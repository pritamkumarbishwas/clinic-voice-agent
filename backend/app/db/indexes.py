import logging

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.db.mongo import (
    appointments,
    benchmark_runs,
    call_turns,
    calls,
    clinic_knowledge,
    doctors,
    slots,
    users,
)

logger = logging.getLogger("clinic-indexes")


async def create_indexes() -> None:
    """Create idempotent indexes for the API and agent worker."""
    await users.create_index([("email", ASCENDING)], unique=True)
    await users.create_index([("role", ASCENDING), ("active", ASCENDING)])

    await doctors.create_index([("name", ASCENDING)])
    await doctors.create_index([("active", ASCENDING), ("name", ASCENDING)])

    await clinic_knowledge.create_index([("active", ASCENDING)])
    await clinic_knowledge.create_index(
        [("category", ASCENDING), ("active", ASCENDING)]
    )
    await clinic_knowledge.create_index([("updated_at", DESCENDING)])

    await slots.create_index([("status", ASCENDING), ("start_at", ASCENDING)])
    try:
        await slots.create_index(
            [("doctor_id", ASCENDING), ("start_at", ASCENDING)],
            unique=True,
            name="uniq_doctor_slot",
        )
    except (DuplicateKeyError, OperationFailure):
        logger.warning(
            "Could not create unique doctor slot index; duplicate slots exist "
            "or an equivalent index already exists. Run "
            "scripts/ops/migrate_slot_indexes.py to remove duplicates."
        )
        await slots.create_index(
            [("doctor_id", ASCENDING), ("start_at", ASCENDING)],
            name="doctor_id_1_start_at_1",
        )

    await appointments.create_index([("slot_id", ASCENDING)], unique=True)
    await appointments.create_index([("call_id", ASCENDING)])
    await appointments.create_index([("created_at", DESCENDING)])
    await appointments.create_index([("start_at", ASCENDING)])
    await appointments.create_index(
        [("status", ASCENDING), ("start_at", ASCENDING)]
    )
    await appointments.create_index(
        [("doctor_name", ASCENDING), ("created_at", DESCENDING)]
    )
    await appointments.create_index(
        [("status", ASCENDING), ("created_at", DESCENDING)]
    )

    await calls.create_index([("call_id", ASCENDING)], unique=True)
    await calls.create_index([("started_at", DESCENDING)])
    await calls.create_index([("analysis_status", ASCENDING)])
    await calls.create_index(
        [("run_id", ASCENDING), ("started_at", DESCENDING)]
    )
    await calls.create_index(
        [("booking_outcome", ASCENDING), ("started_at", DESCENDING)]
    )
    await calls.create_index(
        [("sentiment", ASCENDING), ("started_at", DESCENDING)]
    )
    await calls.create_index(
        [
            ("run_id", ASCENDING),
            ("booking_outcome", ASCENDING),
            ("started_at", DESCENDING),
        ]
    )

    await call_turns.create_index(
        [("call_id", ASCENDING), ("started_at", ASCENDING)]
    )
    await call_turns.create_index(
        [("call_id", ASCENDING), ("turn_id", ASCENDING)]
    )
    await call_turns.create_index([("started_at", DESCENDING)])
    await call_turns.create_index(
        [("run_id", ASCENDING), ("started_at", DESCENDING)]
    )

    await benchmark_runs.create_index([("run_id", ASCENDING)], unique=True)
    await benchmark_runs.create_index([("created_at", DESCENDING)])
