from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import CurrentUser, require_admin
from app.repositories import calls as calls_repository

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
    query: dict = {}

    if run_id:
        query["run_id"] = run_id
    if outcome:
        query["booking_outcome"] = outcome
    if sentiment:
        query["sentiment"] = sentiment

    return await calls_repository.list_calls_page(query, page, page_size)


@router.get("/{call_id}")
async def get_call(
    call_id: str,
    _: CurrentUser = Depends(require_admin),
):
    detail = await calls_repository.get_call_detail(call_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Call not found")
    return detail


@router.post("/{call_id}/analyze")
async def requeue_analysis(
    call_id: str,
    _: CurrentUser = Depends(require_admin),
):
    if not await calls_repository.requeue_analysis(call_id):
        raise HTTPException(status_code=404, detail="Call not found")

    return {
        "ok": True,
        "call_id": call_id,
        "analysis_status": "pending",
    }
