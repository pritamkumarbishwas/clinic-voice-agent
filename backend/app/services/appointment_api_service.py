import hashlib
import logging
from datetime import datetime
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.database import appointments
from app.services.booking_service import (
    CLINIC_TZ,
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
)

logger = logging.getLogger("clinic-appointment-api")


def _fingerprint(name: str, phone: str, slot_id: str) -> str:
    payload = "|".join(
        value.strip().casefold() for value in (name, phone, slot_id)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _appointment_payload(document: dict) -> dict:
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
    return {
        "ok": True,
        "appointment_id": str(document.get("_id", "")),
        "reference": document.get("reference", ""),
        "doctor": document.get("doctor_name", ""),
        "name": document.get("name", ""),
        "date": start_local.date().isoformat() if start_local else None,
        "start_at": start_local.isoformat() if start_local else None,
        "end_at": end_local.isoformat() if end_local else None,
        "local_time": (
            start_local.strftime("%I:%M %p").lstrip("0")
            if start_local
            else None
        ),
        "status": document.get("status", ""),
    }


def _with_idempotency(
    payload: dict,
    key: str,
    *,
    replay: bool,
) -> dict:
    return {
        **payload,
        "idempotency_key": key,
        "idempotent_replay": replay,
    }


async def create_appointment(
    *,
    name: str,
    phone: str,
    slot_id: str,
    idempotency_key: str | None = None,
    voice_session_room: str | None = None,
) -> dict:
    key = (idempotency_key or "").strip()
    if not key:
        key = f"api-{uuid4().hex}"
    fingerprint = _fingerprint(name, phone, slot_id)

    try:
        existing = await appointments.find_one(
            {"api_idempotency_key": key}
        )
    except PyMongoError:
        logger.exception("Idempotency lookup failed")
        return {
            "ok": False,
            "code": "BOOKING_ERROR",
            "message": "Booking could not be verified.",
        }

    if existing is not None:
        if existing.get("api_idempotency_fingerprint") != fingerprint:
            return {
                "ok": False,
                "code": "IDEMPOTENCY_CONFLICT",
                "message": "Idempotency key already used.",
            }
        return _with_idempotency(
            _appointment_payload(existing),
            key,
            replay=True,
        )

    result = await book_appointment(
        name=name,
        phone=phone,
        slot_id=slot_id,
        call_id=f"api-{uuid4().hex}",
        extra_fields={
            "api_idempotency_key": key,
            "api_idempotency_fingerprint": fingerprint,
            "source": "voice" if voice_session_room else "api",
            "voice_session_room": voice_session_room,
        },
    )

    if result.get("ok"):
        return _with_idempotency(result, key, replay=False)

    if result.get("code") == "IDEMPOTENCY_CONFLICT":
        try:
            existing = await appointments.find_one(
                {"api_idempotency_key": key}
            )
        except PyMongoError:
            logger.exception("Idempotency conflict lookup failed")
            return {
                "ok": False,
                "code": "BOOKING_ERROR",
                "message": "Booking could not be verified.",
            }
        if (
            existing is not None
            and existing.get("api_idempotency_fingerprint") == fingerprint
        ):
            return _with_idempotency(
                _appointment_payload(existing),
                key,
                replay=True,
            )

    return result


def _object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


async def _find_appointment(appointment_id: str) -> dict | None:
    object_id = _object_id(appointment_id)
    if object_id is None:
        return None
    return await appointments.find_one({"_id": object_id})


async def cancel_appointment_by_id(
    appointment_id: str,
    *,
    reason: str = "admin_request",
) -> dict:
    appointment = await _find_appointment(appointment_id)
    if appointment is None:
        return {
            "ok": False,
            "code": "APPOINTMENT_NOT_FOUND",
            "message": "Appointment not found.",
        }

    result = await cancel_appointment(
        reference=appointment.get("reference")
        or str(appointment.get("_id", "")),
        phone=appointment.get("phone", ""),
        call_id=appointment.get("call_id"),
        reason=reason,
    )
    if result.get("ok"):
        result["appointment_id"] = str(appointment["_id"])
    return result


async def reschedule_appointment_by_id(
    appointment_id: str,
    *,
    new_slot_id: str,
) -> dict:
    appointment = await _find_appointment(appointment_id)
    if appointment is None:
        return {
            "ok": False,
            "code": "APPOINTMENT_NOT_FOUND",
            "message": "Appointment not found.",
        }

    result = await reschedule_appointment(
        reference=appointment.get("reference")
        or str(appointment.get("_id", "")),
        phone=appointment.get("phone", ""),
        new_slot_id=new_slot_id,
        call_id=appointment.get("call_id"),
    )
    if result.get("ok"):
        result["appointment_id"] = str(appointment["_id"])
    return result
