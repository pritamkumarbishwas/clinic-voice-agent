import asyncio
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from app.config import sanitize_run_id, settings
from app.core.errors import ApiError
from app.db.mongo import appointments, call_turns, calls

MAX_RANGE_DAYS = 366
DEFAULT_RANGE_DAYS = 30


def _day_bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(
        from_date, time.min, tzinfo=settings.clinic_timezone
    ).astimezone(timezone.utc)
    end = datetime.combine(
        to_date + timedelta(days=1),
        time.min,
        tzinfo=settings.clinic_timezone,
    ).astimezone(timezone.utc)
    return start, end


def _number(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _count(row: dict, key: str) -> int:
    return int(row.get(key) or 0)


def _build_summary(
    *,
    from_date: date,
    to_date: date,
    run_id: str | None,
    call_row: dict | None,
    appointment_rows: list[dict],
    turn_row: dict | None,
) -> dict:
    call_row = call_row or {}
    turn_row = turn_row or {}

    total_calls = _count(call_row, "total")
    booked = _count(call_row, "booked")
    cancelled = _count(call_row, "cancelled")
    not_booked = _count(call_row, "not_booked")
    positive = _count(call_row, "positive")
    neutral = _count(call_row, "neutral")
    negative = _count(call_row, "negative")
    unknown = _count(call_row, "unknown")

    by_outcome = {
        "booked": booked,
        "cancelled": cancelled,
        "not_booked": not_booked,
    }
    by_outcome["unknown"] = max(0, total_calls - sum(by_outcome.values()))

    by_sentiment = {
        "positive": positive,
        "neutral": neutral,
        "negative": negative,
        "unknown": unknown,
    }
    by_sentiment["unknown"] += max(
        0, total_calls - sum(by_sentiment.values())
    )

    by_status = {
        str(row.get("_id") or "unknown"): int(row.get("count") or 0)
        for row in appointment_rows
    }
    total_appointments = sum(by_status.values())

    duration_ms = call_row.get("avg_duration_ms")
    return {
        "range": {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "run_id": run_id,
        },
        "calls": {
            "total": total_calls,
            "completed": _count(call_row, "completed"),
            "average_duration_seconds": (
                round(float(duration_ms) / 1000, 2)
                if duration_ms is not None
                else None
            ),
            "by_outcome": by_outcome,
            "by_sentiment": by_sentiment,
        },
        "appointments": {
            "total": total_appointments,
            "by_status": by_status,
        },
        "booking_conversion_rate": (
            round(booked / total_calls, 4) if total_calls else 0.0
        ),
        "latency": {
            "turn_count": _count(turn_row, "turn_count"),
            "average_ms": {
                "stt": _number(turn_row.get("avg_stt_latency_ms")),
                "llm": _number(turn_row.get("avg_llm_latency_ms")),
                "tts": _number(turn_row.get("avg_tts_latency_ms")),
                "end_to_audio": _number(
                    turn_row.get("avg_end_to_audio_ms")
                ),
            },
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_analytics_summary(
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    run_id: str | None = None,
) -> dict:
    today = datetime.now(settings.clinic_timezone).date()
    end_date = to_date or today
    start_date = from_date or end_date - timedelta(
        days=DEFAULT_RANGE_DAYS - 1
    )

    if start_date > end_date:
        raise ApiError(
            status_code=422,
            code="INVALID_DATE_RANGE",
            message="The start date must be before the end date.",
        )
    if (end_date - start_date).days >= MAX_RANGE_DAYS:
        raise ApiError(
            status_code=422,
            code="DATE_RANGE_TOO_LARGE",
            message=f"The date range cannot exceed {MAX_RANGE_DAYS} days.",
        )

    clean_run_id = None
    if run_id is not None:
        clean_run_id = sanitize_run_id(run_id)
        if clean_run_id is None:
            raise ApiError(
                status_code=422,
                code="INVALID_RUN_ID",
                message="run_id is invalid.",
            )

    start, end = _day_bounds(start_date, end_date)
    call_match: dict = {"started_at": {"$gte": start, "$lt": end}}
    turn_match: dict = {"started_at": {"$gte": start, "$lt": end}}
    appointment_match: dict = {
        "created_at": {"$gte": start, "$lt": end}
    }
    if clean_run_id:
        call_match["run_id"] = clean_run_id
        turn_match["run_id"] = clean_run_id

    call_pipeline = [
        {"$match": call_match},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "completed": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$analysis_status", "completed"]},
                            1,
                            0,
                        ]
                    }
                },
                "booked": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$booking_outcome", "booked"]},
                            1,
                            0,
                        ]
                    }
                },
                "cancelled": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$booking_outcome", "cancelled"]},
                            1,
                            0,
                        ]
                    }
                },
                "not_booked": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$booking_outcome", "not_booked"]},
                            1,
                            0,
                        ]
                    }
                },
                "positive": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$sentiment", "positive"]},
                            1,
                            0,
                        ]
                    }
                },
                "neutral": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$sentiment", "neutral"]},
                            1,
                            0,
                        ]
                    }
                },
                "negative": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$sentiment", "negative"]},
                            1,
                            0,
                        ]
                    }
                },
                "unknown": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$sentiment", "unknown"]},
                            1,
                            0,
                        ]
                    }
                },
                "avg_duration_ms": {
                    "$avg": {"$subtract": ["$ended_at", "$started_at"]}
                },
            }
        },
    ]

    appointment_pipeline = [
        {"$match": appointment_match},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]

    turn_pipeline = [
        {"$match": turn_match},
        {
            "$group": {
                "_id": None,
                "turn_count": {"$sum": 1},
                "avg_stt_latency_ms": {"$avg": "$stt_latency_ms"},
                "avg_llm_latency_ms": {"$avg": "$llm_latency_ms"},
                "avg_tts_latency_ms": {"$avg": "$tts_latency_ms"},
                "avg_end_to_audio_ms": {"$avg": "$end_to_audio_ms"},
            }
        },
    ]

    call_rows, appointment_rows, turn_rows = await asyncio.gather(
        calls.aggregate(call_pipeline).to_list(length=1),
        appointments.aggregate(appointment_pipeline).to_list(length=100),
        call_turns.aggregate(turn_pipeline).to_list(length=1),
    )

    return _build_summary(
        from_date=start_date,
        to_date=end_date,
        run_id=clean_run_id,
        call_row=call_rows[0] if call_rows else None,
        appointment_rows=appointment_rows,
        turn_row=turn_rows[0] if turn_rows else None,
    )
