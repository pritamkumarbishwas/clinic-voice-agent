import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import clinic, close_database, initialize_database

CLINIC_PROFILE = {
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


async def seed_clinic(force: bool = False) -> None:
    await initialize_database()

    try:
        existing = await clinic.find_one({"_id": "main"})
        if existing and not force:
            print(
                "Clinic profile already exists. Use --force to overwrite it."
            )
            return

        await clinic.update_one(
            {"_id": "main"},
            {
                "$set": {
                    **CLINIC_PROFILE,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        print("Clinic profile seeded successfully.")
    finally:
        await close_database()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed or overwrite the clinic profile."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing clinic profile.",
    )
    args = parser.parse_args()
    asyncio.run(seed_clinic(force=args.force))


if __name__ == "__main__":
    main()
