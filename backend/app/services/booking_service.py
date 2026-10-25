import logging
import os
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from app.database import appointments, calls, client, doctors, slots

logger = logging.getLogger("clinic-booking")

CLINIC_TZ = ZoneInfo(os.getenv("CLINIC_TIMEZONE", "Asia/Kolkata"))
MAX_SLOTS_PER_DATE = 15

_PHONE_PATTERN = re.compile(r"^\+?\d{10,15}$")
_DOCTOR_PREFIX_PATTERN = re.compile(r"^(?:dr\.?|doctor)\s+", re.IGNORECASE)
_PHONE_NOISE_PATTERN = re.compile(r"[\s\-().]")


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _normalize_phone(value: str) -> str | None:
    cleaned = _PHONE_NOISE_PATTERN.sub("", _clean_text(value))
    return cleaned if _PHONE_PATTERN.fullmatch(cleaned) else None


def _normalize_doctor_name(value: str) -> str:
    cleaned = _clean_text(value)
    stripped = _DOCTOR_PREFIX_PATTERN.sub("", cleaned).strip()
    return stripped or cleaned


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
            "name": {"$regex": pattern, "$options": "i"},
            "active": True,
        }
    )


def _local_to_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


async def check_availability(date: str, doctor_name: str) -> dict:
    """Return real, future, available slots for a doctor on a local clinic date."""
    try:
        requested_date = datetime.strptime(_clean_text(date), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return {"ok": False, "message": "Use date format YYYY-MM-DD."}

    doctor = await _find_doctor(doctor_name)
    if not doctor:
        return {
            "ok": False,
            "message": (
                f"No active doctor matched '{_clean_text(doctor_name)}'. "
                "Ask the caller which doctor they want."
            ),
        }

    day_start = datetime.combine(requested_date, time.min, tzinfo=CLINIC_TZ)
    day_end = day_start + timedelta(days=1)
    now = datetime.now(timezone.utc)

    cursor = (
        slots.find(
            {
                "doctor_id": doctor["_id"],
                "start_at": {
                    "$gte": _local_to_utc(day_start),
                    "$lt": _local_to_utc(day_end),
                },
                "status": "available",
            }
        )
        .sort("start_at", 1)
        .limit(MAX_SLOTS_PER_DATE)
    )

    results = []
    async for slot in cursor:
        if slot["start_at"] <= now:
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
            "message": "Ask the caller for their full name before booking.",
        }

    if not clean_phone:
        return {
            "ok": False,
            "message": "Ask for a valid phone number with 10 to 15 digits.",
        }

    try:
        slot_object_id = ObjectId(slot_id)
    except (InvalidId, TypeError):
        return {"ok": False, "message": "Invalid appointment slot."}

    appointment_object_id = ObjectId()

    async def _transaction(session) -> dict:
        existing = await appointments.find_one(
            {"call_id": call_id, "slot_id": slot_object_id},
            session=session,
        )
        if existing:
            return {
                "ok": True,
                "appointment_id": str(existing["_id"]),
                "message": "Appointment was already booked for this call.",
            }

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
                "message": "That slot is no longer available. Check availability again.",
            }

        doctor = await doctors.find_one({"_id": slot["doctor_id"]}, session=session)
        doctor_name = doctor["name"] if doctor else None

        await appointments.insert_one(
            {
                "_id": appointment_object_id,
                "slot_id": slot_object_id,
                "doctor_id": slot["doctor_id"],
                "doctor_name": doctor_name,
                "name": clean_name,
                "phone": clean_phone,
                "start_at": slot["start_at"],
                "end_at": slot["end_at"],
                "call_id": call_id,
                "status": "confirmed",
                "created_at": datetime.now(timezone.utc),
            },
            session=session,
        )

        await calls.update_one(
            {"call_id": call_id},
            {
                "$set": {
                    "booking_outcome": "booked",
                    "appointment_id": str(appointment_object_id),
                }
            },
            session=session,
        )

        return {
            "ok": True,
            "appointment_id": str(appointment_object_id),
            "doctor": doctor_name,
            "start_at": slot["start_at"].astimezone(CLINIC_TZ).isoformat(),
            "message": "Appointment booked.",
        }

    try:
        async with await client.start_session() as session:
            return await session.with_transaction(_transaction)
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
