"""Install Phase 4 API indexes idempotently.

Run from the backend directory:

    python scripts/ops/migrate_phase4_api.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.mongo import close_database, initialize_database  # noqa: E402


async def run() -> None:
    try:
        await initialize_database()
        print("Phase 4 API indexes are up to date.")
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(run())
