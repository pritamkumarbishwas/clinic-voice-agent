import logging
import re
import secrets
from datetime import datetime, time, timedelta, timezone
from functools import partial

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.config import settings
from app.database import appointments, calls, client, doctors, slots
from app.services.clinic_service import (
    closed_holiday_for_date,
    get_clinic_profile,
)

logger = logging.getLogger("clinic-booking")

CLINIC_TZ = settings.clinic_timezone
MAX_SLOTS_PER_DATE = 15
BOOKING_REFERENCE_PREFIX = "CLN"
BOOKING_REFERENCE_LENGTH = 6
MAX_REFERENCE_ATTEMPTS = 8
BOOKING_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

_PHONE_PATTERN = re.compile(r"^\+?\d{10,15}$")
_DOCTOR_PREFIX_PATTERN = re.compile(r"^(?:dr\.?|doctor)\s+", re.IGNORECASE)
_PHONE_NOISE_PATTERN = re.compile(r"[\s\-().]")
_REFERENCE_NOISE_PATTERN = re.compile(r"[\s\-.]")
_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _normalize_digits(value: str) -> str:
    return (value or "").translate(_DEVANAGARI_DIGITS)


def _normalize_phone(value: str) -> str | None:
    cleaned = _PHONE_NOISE_PATTERN.sub(
        "", _normalize_digits(_clean_text(value))
    )
    return cleaned if _PHONE_PATTERN.fullmatch(cleaned) else None


def _normalize_doctor_name(value: str) -> str:
    cleaned = _clean_text(value)
    stripped = _DOCTOR_PREFIX_PATTERN.sub("", cleaned).strip()
    return stripped or cleaned


def generate_booking_reference() -> str:
    code = "".join(
        secrets.choice(BOOKING_REFERENCE_ALPHABET)
        for _ in range(BOOKING_REFERENCE_LENGTH)
    )
    return f"{BOOKING_REFERENCE_PREFIX}-{code}"


def normalize_booking_reference(value: str | None) -> str | None:
    cleaned = _normalize_digits(_clean_text(value)).upper()
    if (
        cleaned.startswith(BOOKING_REFERENCE_PREFIX)
        and len(cleaned) > BOOKING_REFERENCE_LENGTH
    ):
        cleaned = cleaned[len(BOOKING_REFERENCE_PREFIX) :]
    cleaned = _REFERENCE_NOISE_PATTERN.sub("", cleaned)
    if len(cleaned) != BOOKING_REFERENCE_LENGTH:
        return None
    if any(char not in BOOKING_REFERENCE_ALPHABET for char in cleaned):
        return None
    return f"{BOOKING_REFERENCE_PREFIX}-{cleaned}"


def _appointment_reference(document: dict) -> str:
    return document.get("reference") or str(document.get("_id", ""))


def _phone_lookup_values(phone: str) -> list[str]:
    digits = phone.removeprefix("+")
    values = [phone, digits, f"+{digits}"]
    if len(digits) == 12 and digits.startswith("91"):
        values.append(digits[2:])
    elif len(digits) == 11 and digits.startswith("0"):
        values.append(digits[1:])
    elif len(digits) == 10:
        values.extend([f"91{digits}", f"+91{digits}", f"0{digits}"])
    return list(dict.fromkeys(values))


def _appointment_lookup_filter(reference: str | None) -> dict | None:
    canonical = normalize_booking_reference(reference)
    if canonical:
        return {"reference": canonical}
    try:
        return {"_id": ObjectId(_clean_text(reference))}
    except (InvalidId, TypeError):
        return None


def _parse_clock(value) -> time | None:
    if not value:
        return None
    try:
        return time.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _is_past(value, now: datetime) -> bool:
    if not isinstance(value, datetime):
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= now


async def _load_clinic_profile() -> dict | None:
    try:
        return await get_clinic_profile()
    except Exception:
        logger.exception("Could not load clinic profile for booking validation")
        return None


def _slot_validation_error(
    slot: dict | None,
    doctor: dict | None,
    profile: dict | None,
    now: datetime,
) -> str | None:
    if not slot or slot.get("status") != "available":
        return "SLOT_UNAVAILABLE"
    start_at = slot.get("start_at")
    if not isinstance(start_at, datetime) or _is_past(start_at, now):
        return "SLOT_UNAVAILABLE"
    end_at = slot.get("end_at")
    if isinstance(end_at, datetime) and end_at <= start_at:
        return "SLOT_UNAVAILABLE"
    if not doctor or not doctor.get("active"):
        return "DOCTOR_UNAVAILABLE"

    local_start = start_at.astimezone(CLINIC_TZ)
    local_end = (
        end_at.astimezone(CLINIC_TZ)
        if isinstance(end_at, datetime)
        else local_start + timedelta(minutes=30)
    )

    if profile:
        holiday = closed_holiday_for_date(profile, local_start.date())
        if holiday is not None:
            return "CLINIC_CLOSED"
        hours = profile.get("hours") or {}
        open_time = _parse_clock(hours.get("open"))
        close_time = _parse_clock(hours.get("close"))
        if open_time and local_start.time() < open_time:
            return "SLOT_OUTSIDE_CLINIC_HOURS"
        if close_time and local_end.time() > close_time:
            return "SLOT_OUTSIDE_CLINIC_HOURS"

    working_days = doctor.get("working_days")
    if working_days and local_start.weekday() not in working_days:
        return "SLOT_OUTSIDE_DOCTOR_SCHEDULE"

    doctor_start = _parse_clock(doctor.get("start_time"))
    doctor_end = _parse_clock(doctor.get("end_time"))
    if doctor_start and local_start.time() < doctor_start:
        return "SLOT_OUTSIDE_DOCTOR_SCHEDULE"
    if doctor_end and local_end.time() > doctor_end:
        return "SLOT_OUTSIDE_DOCTOR_SCHEDULE"
    return None


def _slot_error_message(code: str) -> str:
    if code == "CLINIC_CLOSED":
        return "Clinic is closed on that date. Offer another date."
    if code == "SLOT_OUTSIDE_CLINIC_HOURS":
        return "That slot is outside clinic hours. Offer another slot."
    if code == "SLOT_OUTSIDE_DOCTOR_SCHEDULE":
        return "That slot is outside the doctor's schedule. Offer another slot."
    if code == "DOCTOR_UNAVAILABLE":
        return "That doctor is not available. Offer another doctor."
    return "That slot is no longer available. Check availability again."


def _patient_appointment_payload(
    document: dict,
    *,
    message: str | None = None,
) -> dict:
    start_at = document.get("start_at")
    end_at = document.get("end_at")
    start_local = (
        start_at.astimezone(CLINIC_TZ)
        if isinstance(start_at, datetime)
        else None
    )
    end_local = (
        end_at.astimezone(CLINIC_TZ)
        if isinstance(end_at, datetime)
        else None
    )
    payload = {
        "ok": True,
        "reference": _appointment_reference(document),
        "doctor": document.get("doctor_name"),
        "name": document.get("name"),
        "date": start_local.date().isoformat() if start_local else None,
        "start_at": start_local.isoformat() if start_local else None,
        "end_at": end_local.isoformat() if end_local else None,
        "local_time": (
            start_local.strftime("%I:%M %p").lstrip("0")
            if start_local
            else None
        ),
        "status": document.get("status"),
    }
    if message:
        payload["message"] = message
    return payload


def _booking_success_payload(document: dict, *, message: str) -> dict:
    start_at = document.get("start_at")
    start_local = (
        start_at.astimezone(CLINIC_TZ)
        if isinstance(start_at, datetime)
        else None
    )
    return {
        "ok": True,
        "appointment_id": str(document.get("_id", "")),
        "reference": _appointment_reference(document),
        "doctor": document.get("doctor_name"),
        "start_at": start_local.isoformat() if start_local else None,
        "local_time": (
            start_local.strftime("%I:%M %p").lstrip("0")
            if start_local
            else None
        ),
        "message": message,
    }


def _appointment_not_found() -> dict:
    return {
        "ok": False,
        "code": "APPOINTMENT_NOT_FOUND",
        "message": (
            "Appointment could not be verified. Do not say whether the "
            "reference or phone exists. Ask the caller to check both."
        ),
    }


def _invalid_phone() -> dict:
    return {
        "ok": False,
        "code": "INVALID_PHONE",
        "message": "Ask for a valid phone number with 10 to 15 digits.",
    }


class _AppointmentActionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _action_error(code: str, message: str) -> dict:
    return {"ok": False, "code": code, "message": message}


async def _find_patient_appointment(
    reference: str,
    phone: str,
    *,
    session=None,
) -> dict | None:
    lookup = _appointment_lookup_filter(reference)
    if lookup is None:
        return None
    query = {"phone": {"$in": _phone_lookup_values(phone)}, **lookup}
    return await appointments.find_one(query, session=session)


def format_doctor_roster(doctor_docs: list[dict]) -> str:
    lines = []
    for doctor in doctor_docs:
        name = _clean_text(doctor.get("name") or "")
        if not name:
            continue
        specialty = _clean_text(doctor.get("specialty") or "")
        lines.append(f"- {name}" + (f" ({specialty})" if specialty else ""))
    return "\n".join(lines) if lines else "No doctors are configured."


def format_stt_prompt(doctor_docs: list[dict]) -> str:
    base = (
        "Hindi or Hinglish clinic appointment call. "
        "Recognize doctor names, patient names, weekdays, dates, times, "
        "and phone numbers accurately."
    )
    names = [
        _clean_text(doctor.get("name") or "")
        for doctor in doctor_docs
    ]
    names = [name for name in names if name][:20]
    return f"{base} Doctors: {', '.join(names)}." if names else base


async def get_doctor_directory() -> list[dict]:
    return (
        await doctors.find(
            {"active": True},
            {"_id": 0, "name": 1, "specialty": 1},
        )
        .sort("name", 1)
        .to_list(length=100)
    )


async def get_doctor_roster() -> str:
    return format_doctor_roster(await get_doctor_directory())


async def _find_doctor(doctor_name: str) -> dict | None:
    normalized = _normalize_doctor_name(doctor_name)
    if not normalized:
        return None

    pattern = re.escape(normalized)
    doctor = await doctors.find_one(
        {
            "name": {"$regex": f"^{pattern}$", "$options": "i"},
            "active": True,
        }
    )
    if doctor:
        return doctor

    # The LLM usually says "Sharma" while the record is "Dr. Sharma".
    return await doctors.find_one(
        {
            "name": {
                "$regex": f"(^|\\s){pattern}(\\s|$)",
                "$options": "i",
            },
            "active": True,
        }
    )


def _local_to_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


async def check_availability(date: str, doctor_name: str) -> dict:
    """Return real, future, available slots for a doctor on a local clinic date."""
    try:
        requested_date = datetime.strptime(
            _normalize_digits(_clean_text(date)), "%Y-%m-%d"
        ).date()
    except (TypeError, ValueError):
        return {
            "ok": False,
            "code": "INVALID_DATE",
            "message": "Use date format YYYY-MM-DD.",
        }

    profile = await _load_clinic_profile()
    holiday = (
        closed_holiday_for_date(profile, requested_date)
        if profile is not None
        else None
    )
    if holiday is not None:
        return {
            "ok": False,
            "code": "CLINIC_CLOSED",
            "date": requested_date.isoformat(),
            "slots": [],
            "message": (
                f"Clinic is closed on {requested_date.isoformat()} "
                f"({holiday.name}). Offer another date."
            ),
        }

    doctor = await _find_doctor(doctor_name)
    if not doctor:
        return {
            "ok": False,
            "code": "DOCTOR_NOT_FOUND",
            "message": (
                f"No active doctor matched '{_clean_text(doctor_name)}'. "
                "Ask the caller which doctor they want."
            ),
        }

    day_start = datetime.combine(requested_date, time.min, tzinfo=CLINIC_TZ)
    day_end = day_start + timedelta(days=1)
    now = datetime.now(timezone.utc)

    cursor = slots.find(
        {
            "doctor_id": doctor["_id"],
            "start_at": {
                "$gte": _local_to_utc(day_start),
                "$lt": _local_to_utc(day_end),
            },
            "status": "available",
        }
    ).sort("start_at", 1)

    results = []
    async for slot in cursor:
        if _slot_validation_error(slot, doctor, profile, now) is not None:
            continue

        start_local = slot["start_at"].astimezone(CLINIC_TZ)
        results.append(
            {
                "slot_id": str(slot["_id"]),
                "doctor": doctor["name"],
                "specialty": doctor.get("specialty", ""),
                "start_at": start_local.isoformat(),
                "start_at_utc": slot["start_at"].astimezone(timezone.utc).isoformat(),
                "end_at": slot["end_at"].astimezone(CLINIC_TZ).isoformat(),
                "local_time": start_local.strftime("%I:%M %p").lstrip("0"),
            }
        )

        if len(results) >= MAX_SLOTS_PER_DATE:
            break

    return {
        "ok": True,
        "doctor": doctor["name"],
        "date": requested_date.isoformat(),
        "slots": results,
        "message": (
            "Available slots found. Only offer these slot_id values."
            if results
            else "No available slots on that date."
        ),
    }


async def book_appointment(
    *,
    name: str,
    phone: str,
    slot_id: str,
    call_id: str,
) -> dict:
    """Book a slot atomically. Safe to retry; duplicates for a call are reported, not duplicated."""
    clean_name = _clean_text(name)
    clean_phone = _normalize_phone(phone)

    if not clean_name or len(clean_name) < 2:
        return {
            "ok": False,
            "code": "INVALID_NAME",
            "message": "Ask the caller for their full name before booking.",
        }

    if not clean_phone:
        return _invalid_phone()

    try:
        slot_object_id = ObjectId(slot_id)
    except (InvalidId, TypeError):
        return {
            "ok": False,
            "code": "INVALID_SLOT",
            "message": "Invalid appointment slot.",
        }

    now = datetime.now(timezone.utc)
    try:
        existing = await appointments.find_one(
            {
                "call_id": call_id,
                "slot_id": slot_object_id,
                "status": "confirmed",
            }
        )
        if existing:
            return _booking_success_payload(
                existing,
                message="Appointment was already booked for this call.",
            )

        slot_preview = await slots.find_one({"_id": slot_object_id})
        doctor = (
            await doctors.find_one(
                {"_id": slot_preview.get("doctor_id"), "active": True}
            )
            if slot_preview
            else None
        )
    except PyMongoError:
        logger.exception("Could not validate booking slot %s", slot_id)
        return {
            "ok": False,
            "code": "BOOKING_ERROR",
            "message": (
                "Booking could not be verified. Do not claim success. "
                "Check the booking state before retrying."
            ),
        }

    profile = await _load_clinic_profile()
    validation_error = _slot_validation_error(slot_preview, doctor, profile, now)
    if validation_error is not None:
        return {
            "ok": False,
            "code": validation_error,
            "message": _slot_error_message(validation_error),
        }

    async def _transaction(
        session,
        *,
        appointment_object_id: ObjectId,
        reference: str,
    ) -> dict:
        existing = await appointments.find_one(
            {
                "call_id": call_id,
                "slot_id": slot_object_id,
                "status": "confirmed",
            },
            session=session,
        )
        if existing:
            return _booking_success_payload(
                existing,
                message="Appointment was already booked for this call.",
            )

        slot = await slots.find_one_and_update(
            {
                "_id": slot_object_id,
                "status": "available",
                "start_at": {"$gt": datetime.now(timezone.utc)},
            },
            {
                "$set": {
                    "status": "booked",
                    "appointment_id": appointment_object_id,
                }
            },
            return_document=ReturnDocument.AFTER,
            session=session,
        )
        if slot is None:
            return {
                "ok": False,
                "code": "SLOT_UNAVAILABLE",
                "message": (
                    "That slot is no longer available. Check availability again."
                ),
            }

        doctor = await doctors.find_one(
            {"_id": slot["doctor_id"], "active": True},
            session=session,
        )
        if doctor is None:
            raise _AppointmentActionError(
                "DOCTOR_UNAVAILABLE",
                _slot_error_message("DOCTOR_UNAVAILABLE"),
            )

        appointment_document = {
            "_id": appointment_object_id,
            "reference": reference,
            "slot_id": slot_object_id,
            "doctor_id": slot["doctor_id"],
            "doctor_name": doctor["name"],
            "name": clean_name,
            "phone": clean_phone,
            "start_at": slot["start_at"],
            "end_at": slot["end_at"],
            "call_id": call_id,
            "status": "confirmed",
            "created_at": datetime.now(timezone.utc),
        }

        await appointments.insert_one(appointment_document, session=session)

        await calls.update_one(
            {"call_id": call_id},
            {
                "$set": {
                    "booking_outcome": "booked",
                    "appointment_id": str(appointment_object_id),
                    "appointment_reference": reference,
                }
            },
            session=session,
        )

        return _booking_success_payload(
            appointment_document,
            message="Appointment booked.",
        )

    for _attempt in range(MAX_REFERENCE_ATTEMPTS):
        appointment_object_id = ObjectId()
        reference = generate_booking_reference()
        try:
            async with await client.start_session() as session:
                return await session.with_transaction(
                    partial(
                        _transaction,
                        appointment_object_id=appointment_object_id,
                        reference=reference,
                    )
                )
        except DuplicateKeyError:
            logger.warning("Booking reference collision; retrying")
            continue
        except _AppointmentActionError as exc:
            return _action_error(exc.code, exc.message)
        except PyMongoError:
            logger.exception("Booking transaction failed for call %s", call_id)
            return {
                "ok": False,
                "code": "BOOKING_ERROR",
                "message": (
                    "Booking could not be verified. Do not claim success. "
                    "Check the booking state before retrying."
                ),
            }

    logger.error("Could not allocate a unique booking reference")
    return {
        "ok": False,
        "code": "BOOKING_ERROR",
        "message": (
            "Booking could not be verified. Do not claim success. "
            "Check the booking state before retrying."
        ),
    }


async def get_appointment(*, reference: str, phone: str) -> dict:
    """Return a patient appointment only when reference and phone both match."""
    clean_phone = _normalize_phone(phone)
    if not clean_phone:
        return _invalid_phone()

    try:
        appointment = await _find_patient_appointment(reference, clean_phone)
    except PyMongoError:
        logger.exception("Appointment lookup failed")
        return _action_error(
            "APPOINTMENT_ERROR",
            "Appointment could not be verified. Do not claim success.",
        )

    if appointment is None:
        return _appointment_not_found()
    return _patient_appointment_payload(
        appointment,
        message="Appointment verified. Read the reference and details back.",
    )


async def cancel_appointment(
    *,
    reference: str,
    phone: str,
    call_id: str | None = None,
) -> dict:
    """Cancel a future confirmed appointment after reference and phone verification."""
    clean_phone = _normalize_phone(phone)
    if not clean_phone:
        return _invalid_phone()

    now = datetime.now(timezone.utc)
    try:
        appointment = await _find_patient_appointment(reference, clean_phone)
    except PyMongoError:
        logger.exception("Cancellation lookup failed")
        return _action_error(
            "APPOINTMENT_ERROR",
            "Cancellation could not be verified. Do not claim success.",
        )

    if appointment is None:
        return _appointment_not_found()
    if appointment.get("status") == "cancelled":
        return _patient_appointment_payload(
            appointment,
            message="Appointment was already cancelled.",
        )
    if appointment.get("status") != "confirmed":
        return _action_error(
            "APPOINTMENT_NOT_CANCELLABLE",
            "Only a confirmed future appointment can be cancelled. Refer staff.",
        )
    if _is_past(appointment.get("start_at"), now):
        return _action_error(
            "APPOINTMENT_IN_PAST",
            "That appointment has already started or passed. Refer staff.",
        )

    async def _transaction(session) -> dict:
        current = await appointments.find_one(
            {"_id": appointment["_id"], "phone": clean_phone},
            session=session,
        )
        if current is None:
            raise _AppointmentActionError(
                "APPOINTMENT_NOT_FOUND",
                _appointment_not_found()["message"],
            )
        if current.get("status") == "cancelled":
            return _patient_appointment_payload(
                current,
                message="Appointment was already cancelled.",
            )
        if current.get("status") != "confirmed":
            raise _AppointmentActionError(
                "APPOINTMENT_NOT_CANCELLABLE",
                "Only a confirmed future appointment can be cancelled. Refer staff.",
            )
        current_now = datetime.now(timezone.utc)
        if _is_past(current.get("start_at"), current_now):
            raise _AppointmentActionError(
                "APPOINTMENT_IN_PAST",
                "That appointment has already started or passed. Refer staff.",
            )

        updated = await appointments.update_one(
            {"_id": current["_id"], "status": "confirmed"},
            {
                "$set": {
                    "status": "cancelled",
                    "cancelled_at": current_now,
                    "cancellation_reason": "patient_request",
                }
            },
            session=session,
        )
        if updated.modified_count == 0:
            latest = await appointments.find_one(
                {"_id": current["_id"]},
                session=session,
            )
            if latest is not None and latest.get("status") == "cancelled":
                return _patient_appointment_payload(
                    latest,
                    message="Appointment was already cancelled.",
                )
            raise _AppointmentActionError(
                "APPOINTMENT_CONFLICT",
                "The appointment changed during cancellation. Check again.",
            )

        released = await slots.update_one(
            {
                "_id": current.get("slot_id"),
                "appointment_id": current["_id"],
                "status": "booked",
            },
            {"$set": {"status": "available", "appointment_id": None}},
            session=session,
        )
        if released.matched_count == 0:
            slot = await slots.find_one(
                {"_id": current.get("slot_id")},
                session=session,
            )
            if slot is not None and slot.get("status") == "booked":
                raise _AppointmentActionError(
                    "APPOINTMENT_CONFLICT",
                    "The slot could not be released. Refer staff.",
                )

        if call_id:
            await calls.update_one(
                {"call_id": call_id},
                {
                    "$set": {
                        "booking_outcome": "cancelled",
                        "appointment_id": str(current["_id"]),
                        "appointment_reference": _appointment_reference(current),
                    }
                },
                session=session,
            )

        current["status"] = "cancelled"
        current["cancelled_at"] = current_now
        return _patient_appointment_payload(
            current,
            message="Appointment cancelled and slot released.",
        )

    try:
        async with await client.start_session() as session:
            return await session.with_transaction(_transaction)
    except _AppointmentActionError as exc:
        return _action_error(exc.code, exc.message)
    except PyMongoError:
        logger.exception("Cancellation transaction failed")
        return _action_error(
            "APPOINTMENT_ERROR",
            "Cancellation could not be verified. Do not claim success.",
        )


async def reschedule_appointment(
    *,
    reference: str,
    phone: str,
    new_slot_id: str,
    call_id: str | None = None,
) -> dict:
    """Move a future confirmed appointment to another slot for the same doctor."""
    clean_phone = _normalize_phone(phone)
    if not clean_phone:
        return _invalid_phone()

    try:
        new_slot_object_id = ObjectId(new_slot_id)
    except (InvalidId, TypeError):
        return _action_error(
            "INVALID_SLOT",
            "Invalid appointment slot. Check availability again.",
        )

    now = datetime.now(timezone.utc)
    try:
        appointment = await _find_patient_appointment(reference, clean_phone)
    except PyMongoError:
        logger.exception("Reschedule lookup failed")
        return _action_error(
            "APPOINTMENT_ERROR",
            "Reschedule could not be verified. Do not claim success.",
        )

    if appointment is None:
        return _appointment_not_found()
    if appointment.get("status") == "cancelled":
        return _action_error(
            "APPOINTMENT_CANCELLED",
            "That appointment is cancelled. Book a new appointment instead.",
        )
    if appointment.get("status") != "confirmed":
        return _action_error(
            "APPOINTMENT_NOT_RESCHEDULABLE",
            "Only a confirmed future appointment can be rescheduled. Refer staff.",
        )
    if _is_past(appointment.get("start_at"), now):
        return _action_error(
            "APPOINTMENT_IN_PAST",
            "That appointment has already started or passed. Refer staff.",
        )
    if appointment.get("slot_id") == new_slot_object_id:
        return _patient_appointment_payload(
            appointment,
            message="Appointment is already scheduled for that slot.",
        )

    profile = await _load_clinic_profile()

    async def _transaction(session) -> dict:
        current = await appointments.find_one(
            {"_id": appointment["_id"], "phone": clean_phone},
            session=session,
        )
        if current is None:
            raise _AppointmentActionError(
                "APPOINTMENT_NOT_FOUND",
                _appointment_not_found()["message"],
            )
        if current.get("status") == "cancelled":
            raise _AppointmentActionError(
                "APPOINTMENT_CANCELLED",
                "That appointment is cancelled. Book a new appointment instead.",
            )
        if current.get("status") != "confirmed":
            raise _AppointmentActionError(
                "APPOINTMENT_NOT_RESCHEDULABLE",
                "Only a confirmed future appointment can be rescheduled. Refer staff.",
            )
        current_now = datetime.now(timezone.utc)
        if _is_past(current.get("start_at"), current_now):
            raise _AppointmentActionError(
                "APPOINTMENT_IN_PAST",
                "That appointment has already started or passed. Refer staff.",
            )
        if current.get("slot_id") == new_slot_object_id:
            return _patient_appointment_payload(
                current,
                message="Appointment is already scheduled for that slot.",
            )

        new_slot = await slots.find_one(
            {"_id": new_slot_object_id},
            session=session,
        )
        doctor = (
            await doctors.find_one(
                {"_id": new_slot.get("doctor_id"), "active": True},
                session=session,
            )
            if new_slot
            else None
        )
        if new_slot is None:
            raise _AppointmentActionError(
                "SLOT_UNAVAILABLE",
                _slot_error_message("SLOT_UNAVAILABLE"),
            )
        if not doctor:
            raise _AppointmentActionError(
                "DOCTOR_UNAVAILABLE",
                _slot_error_message("DOCTOR_UNAVAILABLE"),
            )
        if doctor.get("_id") != current.get("doctor_id"):
            raise _AppointmentActionError(
                "DOCTOR_MISMATCH",
                "Reschedule to another doctor is not supported. "
                "Cancel and book a new appointment, or refer staff.",
            )

        validation_error = _slot_validation_error(
            new_slot,
            doctor,
            profile,
            current_now,
        )
        if validation_error is not None:
            raise _AppointmentActionError(
                validation_error,
                _slot_error_message(validation_error),
            )

        claimed = await slots.find_one_and_update(
            {
                "_id": new_slot_object_id,
                "status": "available",
                "start_at": {"$gt": datetime.now(timezone.utc)},
            },
            {
                "$set": {
                    "status": "booked",
                    "appointment_id": current["_id"],
                }
            },
            return_document=ReturnDocument.AFTER,
            session=session,
        )
        if claimed is None:
            raise _AppointmentActionError(
                "SLOT_UNAVAILABLE",
                _slot_error_message("SLOT_UNAVAILABLE"),
            )

        released = await slots.update_one(
            {
                "_id": current.get("slot_id"),
                "appointment_id": current["_id"],
                "status": "booked",
            },
            {"$set": {"status": "available", "appointment_id": None}},
            session=session,
        )
        if released.matched_count == 0:
            old_slot = await slots.find_one(
                {"_id": current.get("slot_id")},
                session=session,
            )
            if old_slot is not None and old_slot.get("status") == "booked":
                raise _AppointmentActionError(
                    "APPOINTMENT_CONFLICT",
                    "The old slot could not be released. Refer staff.",
                )

        updated = await appointments.update_one(
            {"_id": current["_id"], "status": "confirmed"},
            {
                "$set": {
                    "slot_id": new_slot_object_id,
                    "doctor_id": claimed["doctor_id"],
                    "doctor_name": doctor["name"],
                    "start_at": claimed["start_at"],
                    "end_at": claimed["end_at"],
                    "rescheduled_at": current_now,
                }
            },
            session=session,
        )
        if updated.modified_count == 0:
            raise _AppointmentActionError(
                "APPOINTMENT_CONFLICT",
                "The appointment changed during rescheduling. Check again.",
            )

        if call_id:
            await calls.update_one(
                {"call_id": call_id},
                {
                    "$set": {
                        "booking_outcome": "rescheduled",
                        "appointment_id": str(current["_id"]),
                        "appointment_reference": _appointment_reference(current),
                    }
                },
                session=session,
            )

        current["slot_id"] = new_slot_object_id
        current["doctor_id"] = claimed["doctor_id"]
        current["doctor_name"] = doctor["name"]
        current["start_at"] = claimed["start_at"]
        current["end_at"] = claimed["end_at"]
        current["rescheduled_at"] = current_now
        return _patient_appointment_payload(
            current,
            message="Appointment rescheduled and old slot released.",
        )

    try:
        async with await client.start_session() as session:
            return await session.with_transaction(_transaction)
    except _AppointmentActionError as exc:
        return _action_error(exc.code, exc.message)
    except PyMongoError:
        logger.exception("Reschedule transaction failed")
        return _action_error(
            "APPOINTMENT_ERROR",
            "Reschedule could not be verified. Do not claim success.",
        )
