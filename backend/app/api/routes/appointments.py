from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
)

from app.api.deps import limiter, optional_voice_session
from app.api.errors import raise_service_error
from app.auth import CurrentUser, require_admin
from app.schemas.appointments import (
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentUpdate,
    AvailabilityResponse,
)
from app.services.appointment_api_service import (
    cancel_appointment_by_id,
    reschedule_appointment_by_id,
)
from app.services.appointment_api_service import (
    create_appointment as api_create_appointment,
)
from app.services.appointment_service import (
    list_appointments as db_list_appointments,
)
from app.services.booking_service import check_availability

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get(
    "/availability",
    response_model=AvailabilityResponse,
)
async def read_availability(
    date: str = Query(..., min_length=10, max_length=10),
    doctor: str = Query(..., min_length=1, max_length=120),
):
    result = await check_availability(date, doctor)
    if not result.get("ok"):
        raise_service_error(result)
    result["message"] = (
        "Available slots found."
        if result.get("slots")
        else "No available slots on that date."
    )
    return result


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=201,
)
@limiter.limit("10/minute")
async def create_appointment(
    request: Request,
    response: Response,
    payload: AppointmentCreate,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
    voice_session: dict | None = Depends(optional_voice_session),
):
    result = await api_create_appointment(
        name=payload.name,
        phone=payload.phone,
        slot_id=payload.slot_id,
        idempotency_key=idempotency_key,
        voice_session_room=(
            voice_session.get("room_name") if voice_session else None
        ),
    )
    if not result.get("ok"):
        raise_service_error(result)

    if result.get("idempotent_replay"):
        response.status_code = 200
    return result


@router.get(
    "",
    response_model=AppointmentListResponse,
)
async def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, max_length=32),
    doctor: str | None = Query(None, max_length=120),
    date_value: str | None = Query(None, alias="date", max_length=10),
    _: CurrentUser = Depends(require_admin),
):
    try:
        return await db_list_appointments(
            page=page,
            page_size=page_size,
            status=status,
            doctor=doctor,
            date_value=date_value,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="date must use YYYY-MM-DD format",
        ) from error


@router.patch(
    "/{appointment_id}",
    response_model=AppointmentResponse,
)
async def update_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    _: CurrentUser = Depends(require_admin),
):
    result = await reschedule_appointment_by_id(
        appointment_id,
        new_slot_id=payload.slot_id,
    )
    if not result.get("ok"):
        raise_service_error(result)
    return result


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
)
async def cancel_appointment(
    appointment_id: str,
    _: CurrentUser = Depends(require_admin),
):
    result = await cancel_appointment_by_id(appointment_id)
    if not result.get("ok"):
        raise_service_error(result)
    return result
