import asyncio
import math

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import CurrentUser, require_admin
from app.db.mongo import appointments, call_turns, calls

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("")
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

    results_task = (
        calls.find(
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
    total_task = calls.count_documents(query)
    results, total = await asyncio.gather(results_task, total_task)

    return {
        "items": results,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 1,
    }


@router.get("/{call_id}")
async def get_call(
    call_id: str,
    _: CurrentUser = Depends(require_admin),
):
    call = await calls.find_one({"call_id": call_id}, {"_id": 0})
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    turns_task = (
        call_turns.find({"call_id": call_id}, {"_id": 0})
        .sort("started_at", 1)
        .to_list(length=500)
    )
    appointment_task = appointments.find_one(
        {"call_id": call_id},
        {"_id": 0, "slot_id": 0, "doctor_id": 0},
    )
    turns, appointment = await asyncio.gather(turns_task, appointment_task)

    return {
        "call": call,
        "turn_metrics": turns,
        "appointment": appointment,
    }


@router.post("/{call_id}/analyze")
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
