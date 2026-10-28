from fastapi import APIRouter, Depends, Query

from app.auth import CurrentUser, require_admin
from app.db.mongo import call_turns, calls
from app.services.latency_report import (
    LATENCY_FIELDS,
    STT_FAILURE_FIELDS,
    build_report,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/runs")
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


@router.get("/latency")
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
            "run_id": 1,
            "booking_outcome": 1,
            "barge_in_count": 1,
            **{field: 1 for field in STT_FAILURE_FIELDS},
        },
    ).to_list(length=10000)

    report = build_report(turns, call_docs)
    report["run_id"] = run_id
    return report
