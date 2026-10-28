import asyncio
import math

from app.db.mongo import appointments, call_turns, calls


async def list_calls_page(
    query: dict,
    page: int,
    page_size: int,
) -> dict:
    skip = (page - 1) * page_size
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


async def get_call_detail(call_id: str) -> dict | None:
    call = await calls.find_one({"call_id": call_id}, {"_id": 0})
    if not call:
        return None

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


async def requeue_analysis(call_id: str) -> bool:
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
    return result.matched_count > 0
