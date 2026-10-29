from typing import NoReturn

from app.core.errors import ApiError

_SERVICE_ERRORS: dict[str, tuple[int, str, str]] = {
    "INVALID_NAME": (
        422,
        "INVALID_NAME",
        "Enter a valid patient name.",
    ),
    "INVALID_PHONE": (
        422,
        "INVALID_PHONE",
        "Enter a valid phone number with 10 to 15 digits.",
    ),
    "INVALID_DATE": (
        422,
        "INVALID_DATE",
        "Use date format YYYY-MM-DD.",
    ),
    "INVALID_SLOT": (
        422,
        "INVALID_SLOT",
        "Select a valid appointment slot.",
    ),
    "DOCTOR_NOT_FOUND": (
        404,
        "DOCTOR_NOT_FOUND",
        "Doctor not found.",
    ),
    "DOCTOR_UNAVAILABLE": (
        409,
        "DOCTOR_UNAVAILABLE",
        "That doctor is not available.",
    ),
    "CLINIC_CLOSED": (
        409,
        "CLINIC_CLOSED",
        "The clinic is closed on that date.",
    ),
    "SLOT_UNAVAILABLE": (
        409,
        "SLOT_UNAVAILABLE",
        "That slot is no longer available.",
    ),
    "SLOT_OUTSIDE_CLINIC_HOURS": (
        409,
        "SLOT_OUTSIDE_CLINIC_HOURS",
        "That slot is outside clinic hours.",
    ),
    "SLOT_OUTSIDE_DOCTOR_SCHEDULE": (
        409,
        "SLOT_OUTSIDE_DOCTOR_SCHEDULE",
        "That slot is outside the doctor's schedule.",
    ),
    "APPOINTMENT_NOT_FOUND": (
        404,
        "APPOINTMENT_NOT_FOUND",
        "Appointment not found.",
    ),
    "APPOINTMENT_CANCELLED": (
        409,
        "APPOINTMENT_CANCELLED",
        "That appointment is already cancelled.",
    ),
    "APPOINTMENT_IN_PAST": (
        409,
        "APPOINTMENT_IN_PAST",
        "That appointment has already started or passed.",
    ),
    "APPOINTMENT_NOT_CANCELLABLE": (
        409,
        "APPOINTMENT_NOT_CANCELLABLE",
        "That appointment cannot be cancelled.",
    ),
    "APPOINTMENT_NOT_RESCHEDULABLE": (
        409,
        "APPOINTMENT_NOT_RESCHEDULABLE",
        "That appointment cannot be rescheduled.",
    ),
    "APPOINTMENT_CONFLICT": (
        409,
        "APPOINTMENT_CONFLICT",
        "The appointment changed while it was being updated.",
    ),
    "IDEMPOTENCY_CONFLICT": (
        409,
        "IDEMPOTENCY_CONFLICT",
        "This idempotency key was already used for a different booking.",
    ),
    "BOOKING_ERROR": (
        503,
        "BOOKING_UNAVAILABLE",
        "Booking is temporarily unavailable. Please try again.",
    ),
    "APPOINTMENT_ERROR": (
        503,
        "APPOINTMENT_UNAVAILABLE",
        "Appointment service is temporarily unavailable. Please try again.",
    ),
}


def raise_service_error(result: dict) -> NoReturn:
    code = str(result.get("code") or "REQUEST_FAILED")
    status_code, api_code, message = _SERVICE_ERRORS.get(
        code,
        (400, code, "The request could not be completed."),
    )
    raise ApiError(
        status_code=status_code,
        code=api_code,
        message=message,
    )
