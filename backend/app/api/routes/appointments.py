from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import CurrentUser, require_admin
from app.services.appointment_service import (
    list_appointments as db_list_appointments,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("")
async def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, max_length=32),
    doctor: str | None = Query(None, max_length=120),
    date: str | None = Query(None, max_length=10),
    _: CurrentUser = Depends(require_admin),
):
    try:
        return await db_list_appointments(
            page=page,
            page_size=page_size,
            status=status,
            doctor=doctor,
            date_value=date,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="date must use YYYY-MM-DD format",
        ) from error
