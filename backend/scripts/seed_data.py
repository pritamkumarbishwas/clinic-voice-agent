import asyncio
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import (
    appointments,
    clinic,
    close_database,
    doctors,
    initialize_database,
    slots,
)
from app.services.booking_service import CLINIC_TZ, generate_booking_reference

DOCTORS = (
    {"name": "Dr. Sharma", "specialty": "General Physician", "active": True},
    {"name": "Dr. Verma", "specialty": "Dentist", "active": True},
    {"name": "Dr. Singh", "specialty": "Dermatologist", "active": True},
)

SLOT_TIMES = ((10, 0), (10, 30), (11, 0), (14, 0), (16, 0))

DEFAULT_CLINIC = {
    "name": "Sunrise Family Clinic",
    "address": "12 MG Road, Bengaluru 560001",
    "phone": "+91 80 4123 4567",
    "hours": {
        "open": "10:00",
        "close": "17:00",
        "days": "Monday to Saturday",
    },
    "consultation_fee": "500 rupees",
    "emergency_note": (
        "For medical emergencies, call 108 or visit the nearest "
        "emergency department."
    ),
}


async def seed() -> None:
    await initialize_database()

    try:
        for doctor in DOCTORS:
            await doctors.update_one(
                {"name": doctor["name"]},
                {"$setOnInsert": doctor},
                upsert=True,
            )

        doctor_docs = await doctors.find({"active": True}).to_list(length=100)

        now = datetime.now(timezone.utc)
        local_now = now.astimezone(CLINIC_TZ)
        days = [
            (local_now + timedelta(days=offset)).date()
            for offset in range(1, 4)
        ]

        for doctor in doctor_docs:
            for day in days:
                for hour, minute in SLOT_TIMES:
                    start_local = datetime.combine(
                        day, time(hour, minute), tzinfo=CLINIC_TZ
                    )
                    start_at = start_local.astimezone(timezone.utc)

                    if start_at <= now:
                        continue

                    await slots.update_one(
                        {
                            "doctor_id": doctor["_id"],
                            "start_at": start_at,
                        },
                        {
                            "$setOnInsert": {
                                "doctor_id": doctor["_id"],
                                "start_at": start_at,
                                "end_at": start_at + timedelta(minutes=30),
                                "status": "available",
                                "appointment_id": None,
                            }
                        },
                        upsert=True,
                    )

        await _seed_booked_slot(now)

        await clinic.update_one(
            {"_id": "main"},
            {
                "$setOnInsert": {
                    **DEFAULT_CLINIC,
                    "updated_at": now,
                }
            },
            upsert=True,
        )

        print("Doctors, slots, and clinic profile seeded successfully.")

    finally:
        await close_database()


async def _seed_booked_slot(now: datetime) -> None:
    """Keep one booked slot so availability filtering is visible in demos."""
    if await appointments.find_one({"name": "Seed Test Patient"}):
        return

    test_doctor = await doctors.find_one({"name": "Dr. Sharma"})
    if not test_doctor:
        return

    test_slot = await slots.find_one(
        {
            "doctor_id": test_doctor["_id"],
            "status": "available",
            "start_at": {"$gt": now},
        }
    )
    if not test_slot:
        return

    appointment_id = ObjectId()

    await slots.update_one(
        {"_id": test_slot["_id"], "status": "available"},
        {
            "$set": {
                "status": "booked",
                "appointment_id": appointment_id,
            }
        },
    )

    await appointments.insert_one(
        {
            "_id": appointment_id,
            "reference": generate_booking_reference(),
            "slot_id": test_slot["_id"],
            "doctor_id": test_doctor["_id"],
            "doctor_name": test_doctor["name"],
            "name": "Seed Test Patient",
            "phone": "+919000000000",
            "start_at": test_slot["start_at"],
            "end_at": test_slot["end_at"],
            "call_id": f"seed-{uuid4().hex[:8]}",
            "status": "confirmed",
            "created_at": now,
        }
    )


if __name__ == "__main__":
    asyncio.run(seed())
