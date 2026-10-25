
import asyncio
from datetime import datetime, timedelta, timezone

from app.database import (
    doctors,
    slots,
    initialize_database,
    close_database,
)
from bson import ObjectId


async def seed():
    await initialize_database()

    try:
        doctor_data = [
            {
                "name": "Dr. Sharma",
                "specialty": "General Physician",
                "active": True,
            },
            {
                "name": "Dr. Verma",
                "specialty": "Dentist",
                "active": True,
            },
            {
                "name": "Dr. Singh",
                "specialty": "Dermatologist",
                "active": True,
            },
        ]

        for doctor in doctor_data:
            await doctors.update_one(
                {"name": doctor["name"]},
                {"$setOnInsert": doctor},
                upsert=True,
            )

        doctor_docs = await doctors.find(
            {"active": True}
        ).to_list(length=100)

        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).date()
        day_after = (now + timedelta(days=2)).date()

        for doctor in doctor_docs:
            for day in [tomorrow, day_after]:
                for hour, minute in [(10, 0), (10, 30), (11, 0), (14, 0)]:
                    start_at = datetime(
                        day.year, day.month, day.day,
                        hour, minute,
                        tzinfo=timezone.utc,
                    )

                    if start_at <= now:
                        continue

                    end_at = start_at + timedelta(minutes=30)

                    await slots.update_one(
                        {
                            "doctor_id": doctor["_id"],
                            "start_at": start_at,
                        },
                        {
                            "$setOnInsert": {
                                "doctor_id": doctor["_id"],
                                "start_at": start_at,
                                "end_at": end_at,
                                "status": "available",
                                "appointment_id": None,
                            }
                        },
                        upsert=True,
                    )

        # Mark one future slot as booked for testing.
        test_doctor = await doctors.find_one(
            {"name": "Dr. Sharma"}
        )
        if test_doctor:
            test_slot = await slots.find_one({
                "doctor_id": test_doctor["_id"],
                "status": "available",
                "start_at": {"$gt": now},
            })
            if test_slot:
                await slots.update_one(
                    {
                        "_id": test_slot["_id"],
                        "status": "available",
                    },
                    {"$set": {"status": "booked"}},
                )

        print("Fake doctors and slots seeded successfully.")

    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(seed())
