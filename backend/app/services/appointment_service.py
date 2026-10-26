import math
import re
from datetime import date, datetime, time, timedelta, timezone

from pymongo import DESCENDING

from app.config import settings
from app.database import appointments, doctors

CLINIC_TZ = settings.clinic_timezone


def parse_clinic_date(value: str) -> date:
    return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()


def day_bounds_utc(value: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(value, time.min, tzinfo=CLINIC_TZ)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
    )


def build_query(
    status: str | None = None,
    doctor: str | None = None,
    date_value: str | None = None,
) -> dict:
    query: dict = {}

    if status and status != "all":
        query["status"] = status

    if doctor and doctor != "all":
        query["doctor_name"] = {
            "$regex": re.escape(doctor.strip()),
            "$options": "i",
        }

    if date_value:
        start_at, end_at = day_bounds_utc(parse_clinic_date(date_value))
        query["start_at"] = {"$gte": start_at, "$lt": end_at}

    return query


def _iso(value) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def serialize_appointment(document: dict) -> dict:
    return {
        "appointment_id": str(document.get("_id", "")),
        "name": document.get("name", ""),
        "phone": document.get("phone", ""),
        "doctor_name": document.get("doctor_name", ""),
        "start_at": _iso(document.get("start_at")),
        "end_at": _iso(document.get("end_at")),
        "status": document.get("status", ""),
        "call_id": document.get("call_id", ""),
        "created_at": _iso(document.get("created_at")),
    }


async def list_appointments(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    doctor: str | None = None,
    date_value: str | None = None,
) -> dict:
    query = build_query(status=status, doctor=doctor, date_value=date_value)
    skip = (page - 1) * page_size

    cursor = (
        appointments.find(query)
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(page_size)
    )
    items = [serialize_appointment(document) async for document in cursor]
    total = await appointments.count_documents(query)

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 1,
    }


async def list_doctors() -> list[dict]:
    cursor = doctors.find(
        {"active": True},
        {"_id": 0, "name": 1, "specialty": 1},
    ).sort("name", 1)
    return [document async for document in cursor]
