import hashlib
import logging
import re
from datetime import date, datetime, time, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pymongo import UpdateOne

from app.config import settings
from app.database import appointments, doctors, slots
from app.services.clinic_service import (
    closed_holiday_for_date,
    get_clinic_profile,
)
from app.services.embedding_service import (
    RagUnavailableError,
    embed_texts,
    rag_available,
)

logger = logging.getLogger("clinic-doctors")

CLINIC_TZ = settings.clinic_timezone
_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DEFAULT_WORKING_DAYS = [0, 1, 2, 3, 4, 5]
DEFAULT_GENERATE_DAYS = 14
MAX_GENERATE_DAYS = 60


class DoctorProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=2, max_length=120)
    specialty: str = Field(default="", max_length=120)
    active: bool = True
    bio: str = Field(default="", max_length=3000)
    languages: list[str] = Field(default_factory=list, max_length=10)
    working_days: list[int] = Field(
        default_factory=lambda: list(DEFAULT_WORKING_DAYS),
        max_length=7,
    )
    start_time: str = "10:00"
    end_time: str = "17:00"
    slot_minutes: int = Field(default=30, ge=10, le=120)

    @field_validator("name", "specialty", "bio")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join((value or "").split())

    @field_validator("languages")
    @classmethod
    def clean_languages(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            label = " ".join((item or "").split())
            key = label.casefold()
            if label and key not in seen:
                seen.add(key)
                cleaned.append(label)
        return cleaned

    @field_validator("working_days")
    @classmethod
    def clean_working_days(cls, value: list[int]) -> list[int]:
        cleaned = sorted(set(value))
        if any(day < 0 or day > 6 for day in cleaned):
            raise ValueError("Working days must be between 0 (Mon) and 6 (Sun)")
        return cleaned

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not _TIME_PATTERN.fullmatch(cleaned):
            raise ValueError("Time must use HH:MM in 24-hour format")
        return cleaned

    @model_validator(mode="after")
    def validate_hours(self):
        if self.start_time >= self.end_time:
            raise ValueError("End time must be after start time")
        return self


def _object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise ValueError("Invalid doctor id") from exc


def _serialize_doctor(document: dict) -> dict:
    profile = DoctorProfile.model_validate(document)
    created_at = document.get("created_at")
    updated_at = document.get("updated_at")
    return {
        "doctor_id": str(document.get("_id", "")),
        "name": profile.name,
        "specialty": profile.specialty,
        "active": profile.active,
        "bio": profile.bio,
        "languages": profile.languages,
        "working_days": profile.working_days,
        "start_time": profile.start_time,
        "end_time": profile.end_time,
        "slot_minutes": profile.slot_minutes,
        "bio_indexed": bool(document.get("bio_embedding")),
        "created_at": (
            created_at.isoformat()
            if isinstance(created_at, datetime)
            else None
        ),
        "updated_at": (
            updated_at.isoformat()
            if isinstance(updated_at, datetime)
            else None
        ),
    }


async def _ensure_unique_name(name: str, exclude_id: ObjectId | None = None) -> None:
    query = {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
    if exclude_id is not None:
        query["_id"] = {"$ne": exclude_id}
    if await doctors.find_one(query, {"_id": 1}):
        raise ValueError("A doctor with this name already exists")


async def _bio_fields(
    bio: str,
    *,
    existing: dict | None = None,
) -> dict:
    cleaned = " ".join((bio or "").split())
    if not cleaned:
        return {
            "bio_embedding": None,
            "bio_embedding_model": "",
            "bio_hash": "",
        }

    existing_hash = (existing or {}).get("bio_hash")
    new_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    if existing_hash == new_hash and existing and existing.get("bio_embedding"):
        return {}

    if not rag_available():
        return {
            "bio_embedding": None,
            "bio_embedding_model": "",
            "bio_hash": new_hash,
        }

    try:
        embedding = (await embed_texts([cleaned]))[0]
    except RagUnavailableError:
        logger.warning("Doctor bio could not be indexed", exc_info=True)
        return {
            "bio_embedding": None,
            "bio_embedding_model": "",
            "bio_hash": new_hash,
        }

    return {
        "bio_embedding": embedding,
        "bio_embedding_model": settings.openai_embedding_model,
        "bio_hash": new_hash,
    }


async def list_doctors(include_inactive: bool = False) -> list[dict]:
    query = {} if include_inactive else {"active": True}
    cursor = doctors.find(query).sort([("active", -1), ("name", 1)])
    return [_serialize_doctor(document) async for document in cursor]


async def get_doctor(doctor_id: str) -> dict:
    object_id = _object_id(doctor_id)
    document = await doctors.find_one({"_id": object_id})
    if document is None:
        raise LookupError("Doctor not found")
    return _serialize_doctor(document)


def _slot_datetimes_for_doctor(
    profile: DoctorProfile,
    start_date: date,
    days: int,
) -> list[datetime]:
    start_hour, start_minute = map(int, profile.start_time.split(":"))
    end_hour, end_minute = map(int, profile.end_time.split(":"))
    results: list[datetime] = []

    for offset in range(days):
        day = start_date + timedelta(days=offset)
        if day.weekday() not in profile.working_days:
            continue
        current = datetime.combine(
            day,
            time(start_hour, start_minute),
            tzinfo=CLINIC_TZ,
        )
        end = datetime.combine(
            day,
            time(end_hour, end_minute),
            tzinfo=CLINIC_TZ,
        )
        while current + timedelta(minutes=profile.slot_minutes) <= end:
            results.append(current.astimezone(timezone.utc))
            current += timedelta(minutes=profile.slot_minutes)
    return results


async def generate_doctor_slots(
    doctor_id: str,
    *,
    days: int = DEFAULT_GENERATE_DAYS,
    prune: bool = True,
) -> dict:
    if days < 1 or days > MAX_GENERATE_DAYS:
        raise ValueError(
            f"days must be between 1 and {MAX_GENERATE_DAYS}"
        )

    object_id = _object_id(doctor_id)
    document = await doctors.find_one({"_id": object_id})
    if document is None:
        raise LookupError("Doctor not found")

    profile = DoctorProfile.model_validate(document)
    if not profile.active:
        return {"created": 0, "removed": 0}

    now = datetime.now(timezone.utc)
    today = datetime.now(CLINIC_TZ).date()
    desired = [
        start
        for start in _slot_datetimes_for_doctor(profile, today, days)
        if start > now
    ]
    desired_set = set(desired)

    try:
        clinic_profile = await get_clinic_profile()
    except Exception:
        logger.exception("Could not load clinic holidays for slots")
        clinic_profile = {}

    filtered: list[datetime] = []
    for start_at in desired:
        local_date = start_at.astimezone(CLINIC_TZ).date()
        if closed_holiday_for_date(clinic_profile, local_date):
            continue
        filtered.append(start_at)
    desired_set = set(filtered)

    operations = [
        UpdateOne(
            {
                "doctor_id": object_id,
                "start_at": start_at,
            },
            {
                "$setOnInsert": {
                    "doctor_id": object_id,
                    "start_at": start_at,
                    "end_at": start_at
                    + timedelta(minutes=profile.slot_minutes),
                    "status": "available",
                    "appointment_id": None,
                }
            },
            upsert=True,
        )
        for start_at in filtered
    ]
    if operations:
        await slots.bulk_write(operations, ordered=False)

    removed = 0
    if prune:
        horizon = now + timedelta(days=days + 1)
        result = await slots.delete_many(
            {
                "doctor_id": object_id,
                "status": "available",
                "start_at": {
                    "$gt": now,
                    "$lt": horizon,
                    "$nin": list(desired_set),
                },
            }
        )
        removed = result.deleted_count

    return {"created": len(filtered), "removed": removed}


async def _remove_future_available_slots(doctor_object_id: ObjectId) -> int:
    result = await slots.delete_many(
        {
            "doctor_id": doctor_object_id,
            "status": "available",
            "start_at": {"$gt": datetime.now(timezone.utc)},
        }
    )
    return result.deleted_count


async def create_doctor(payload: DoctorProfile) -> dict:
    await _ensure_unique_name(payload.name)
    now = datetime.now(timezone.utc)
    bio_fields = await _bio_fields(payload.bio)
    document = {
        **payload.model_dump(),
        "created_at": now,
        "updated_at": now,
        **bio_fields,
    }
    result = await doctors.insert_one(document)
    document["_id"] = result.inserted_id

    if payload.active:
        await generate_doctor_slots(str(result.inserted_id))
    return _serialize_doctor(document)


async def update_doctor(doctor_id: str, payload: DoctorProfile) -> dict:
    object_id = _object_id(doctor_id)
    existing = await doctors.find_one({"_id": object_id})
    if existing is None:
        raise LookupError("Doctor not found")

    await _ensure_unique_name(payload.name, exclude_id=object_id)
    old_profile = DoctorProfile.model_validate(existing)
    bio_fields = await _bio_fields(payload.bio, existing=existing)
    updates = {
        **payload.model_dump(),
        "updated_at": datetime.now(timezone.utc),
        **bio_fields,
    }
    if not payload.bio:
        updates["bio_embedding"] = None
    await doctors.update_one({"_id": object_id}, {"$set": updates})

    if payload.active:
        schedule_changed = (
            payload.working_days != old_profile.working_days
            or payload.start_time != old_profile.start_time
            or payload.end_time != old_profile.end_time
            or payload.slot_minutes != old_profile.slot_minutes
        )
        await generate_doctor_slots(
            doctor_id,
            prune=schedule_changed,
        )
    else:
        await _remove_future_available_slots(object_id)

    document = await doctors.find_one({"_id": object_id})
    return _serialize_doctor(document or {})


async def deactivate_doctor(
    doctor_id: str,
    *,
    cancel_future: bool = False,
) -> dict:
    object_id = _object_id(doctor_id)
    existing = await doctors.find_one({"_id": object_id})
    if existing is None:
        raise LookupError("Doctor not found")

    now = datetime.now(timezone.utc)
    await doctors.update_one(
        {"_id": object_id},
        {
            "$set": {
                "active": False,
                "updated_at": now,
            }
        },
    )
    removed_slots = await _remove_future_available_slots(object_id)

    cancelled = 0
    if cancel_future:
        future_appointments = appointments.find(
            {
                "doctor_id": object_id,
                "status": "confirmed",
                "start_at": {"$gt": now},
            },
            {"_id": 1, "slot_id": 1},
        )
        items = [item async for item in future_appointments]
        if items:
            appointment_ids = [item["_id"] for item in items]
            slot_ids = [item["slot_id"] for item in items]
            result = await appointments.update_many(
                {"_id": {"$in": appointment_ids}},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": now,
                        "cancellation_reason": "doctor_deactivated",
                    }
                },
            )
            cancelled = result.modified_count
            await slots.update_many(
                {"_id": {"$in": slot_ids}},
                {
                    "$set": {"status": "available", "appointment_id": None}
                },
            )

    return {
        "doctor_id": doctor_id,
        "active": False,
        "removed_slots": removed_slots,
        "cancelled_appointments": cancelled,
    }


async def count_future_appointments(doctor_id: str) -> int:
    object_id = _object_id(doctor_id)
    return await appointments.count_documents(
        {
            "doctor_id": object_id,
            "status": "confirmed",
            "start_at": {"$gt": datetime.now(timezone.utc)},
        }
    )
