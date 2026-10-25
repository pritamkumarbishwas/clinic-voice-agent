import asyncio
import logging
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from app.config import settings
from app.database import calls, close_database, initialize_database
from app.services.analytics_worker import process_call

logger = logging.getLogger("clinic-analysis-worker")

STALE_AFTER = timedelta(minutes=10)


def _claim_filter(now: datetime) -> dict:
    stale = now - STALE_AFTER
    return {
        "ended_at": {"$ne": None},
        "$or": [
            {"analysis_status": "pending"},
            {
                "analysis_status": "failed",
                "analysis_attempts": {
                    "$lt": settings.analysis_max_attempts
                },
            },
            {
                "analysis_status": "running",
                "$or": [
                    {"analysis_locked_at": {"$lt": stale}},
                    {"analysis_locked_at": None},
                ],
            },
        ],
    }


async def claim_next_call() -> dict | None:
    now = datetime.now(timezone.utc)
    return await calls.find_one_and_update(
        _claim_filter(now),
        {
            "$set": {
                "analysis_status": "running",
                "analysis_locked_at": now,
                "analysis_error": None,
            },
            "$inc": {"analysis_attempts": 1},
        },
        sort=[("ended_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


async def process_next_call() -> bool:
    call = await claim_next_call()
    if call is None:
        return False

    call_id = call["call_id"]
    try:
        await process_call(call_id)
    except Exception as exc:
        logger.exception("Analysis failed for call %s", call_id)
        await calls.update_one(
            {"call_id": call_id},
            {
                "$set": {
                    "analysis_status": "failed",
                    "analysis_error": str(exc)[:500],
                    "analysis_locked_at": None,
                }
            },
        )
    return True


async def run_worker(poll_seconds: float | None = None) -> None:
    interval = (
        poll_seconds
        if poll_seconds is not None
        else settings.analysis_poll_seconds
    )

    while True:
        try:
            processed = await process_next_call()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Analysis worker loop failed")
            processed = False

        if not processed:
            await asyncio.sleep(interval)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await initialize_database()
    logger.info(
        "Analysis worker started (poll=%ss, max_attempts=%s)",
        settings.analysis_poll_seconds,
        settings.analysis_max_attempts,
    )

    try:
        await run_worker()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await close_database()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
