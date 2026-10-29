from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import CurrentUser, get_optional_user, require_admin
from app.core.errors import ApiError
from app.schemas.doctors import DoctorListResponse
from app.services.doctor_service import (
    DoctorProfile,
    count_future_appointments,
    create_doctor,
    deactivate_doctor,
    generate_doctor_slots,
    get_doctor,
    list_doctors,
    update_doctor,
)

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=DoctorListResponse)
async def read_doctors(
    include_inactive: bool = Query(False),
    user: CurrentUser | None = Depends(get_optional_user),
):
    if include_inactive and (user is None or not user.is_admin):
        raise ApiError(
            status_code=403,
            code="FORBIDDEN",
            message="Admin access required.",
        )
    return {"items": await list_doctors(include_inactive=include_inactive)}


@router.post("")
async def create_doctor_endpoint(
    payload: DoctorProfile,
    _: CurrentUser = Depends(require_admin),
):
    try:
        return await create_doctor(payload)
    except ValueError as exc:
        status_code = 409 if "already exists" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.put("/{doctor_id}")
async def update_doctor_endpoint(
    doctor_id: str,
    payload: DoctorProfile,
    _: CurrentUser = Depends(require_admin),
):
    try:
        return await update_doctor(doctor_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = 409 if "already exists" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/{doctor_id}")
async def deactivate_doctor_endpoint(
    doctor_id: str,
    cancel_future: bool = Query(False),
    _: CurrentUser = Depends(require_admin),
):
    try:
        return await deactivate_doctor(
            doctor_id, cancel_future=cancel_future
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{doctor_id}/future-appointments")
async def doctor_future_appointments(
    doctor_id: str,
    _: CurrentUser = Depends(require_admin),
):
    try:
        await get_doctor(doctor_id)
        return {"count": await count_future_appointments(doctor_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{doctor_id}/slots")
async def generate_doctor_slots_endpoint(
    doctor_id: str,
    days: int = Query(14, ge=1, le=60),
    _: CurrentUser = Depends(require_admin),
):
    try:
        return await generate_doctor_slots(doctor_id, days=days)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
