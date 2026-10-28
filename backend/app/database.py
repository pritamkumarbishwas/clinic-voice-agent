"""Backward-compatible database imports.

New code should import from ``app.db.mongo`` or ``app.db.indexes``.
"""

from app.db.mongo import (
    DATABASE_NAME,
    MONGODB_URI,
    appointments,
    benchmark_runs,
    call_turns,
    calls,
    client,
    clinic,
    clinic_knowledge,
    close_database,
    db,
    doctors,
    initialize_database,
    slots,
    users,
)

__all__ = [
    "DATABASE_NAME",
    "MONGODB_URI",
    "appointments",
    "benchmark_runs",
    "call_turns",
    "calls",
    "client",
    "clinic",
    "clinic_knowledge",
    "close_database",
    "db",
    "doctors",
    "initialize_database",
    "slots",
    "users",
]
