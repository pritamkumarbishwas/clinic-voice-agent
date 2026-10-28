"""Remove duplicate slots and install the unique doctor-slot index.

Run from the backend directory:

    python scripts/ops/migrate_slot_indexes.py
    python scripts/ops/migrate_slot_indexes.py --apply

The default is a dry run. ``--apply`` deletes duplicate slots, keeping a booked
slot when one exists, then creates ``uniq_doctor_slot``.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import settings  # noqa: E402

INDEX_NAME = "uniq_doctor_slot"
INDEX_KEY = [("doctor_id", ASCENDING), ("start_at", ASCENDING)]


async def find_duplicates(slots) -> list[dict]:
    pipeline = [
        {
            "$group": {
                "_id": {
                    "doctor_id": "$doctor_id",
                    "start_at": "$start_at",
                },
                "count": {"$sum": 1},
                "ids": {"$push": "$_id"},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
    ]
    return await slots.aggregate(pipeline).to_list(length=None)


async def run(apply: bool) -> int:
    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.database_timeout_ms,
        tz_aware=True,
        appname="clinic-slot-migration",
    )
    slots = client[settings.mongodb_database]["slots"]

    try:
        duplicates = await find_duplicates(slots)
        print(f"Duplicate doctor/start_at groups: {len(duplicates)}")

        deleted = 0
        for group in duplicates:
            documents = await slots.find(
                {"_id": {"$in": group["ids"]}}
            ).to_list(length=None)
            documents.sort(
                key=lambda document: (
                    document.get("status") != "booked",
                    str(document["_id"]),
                )
            )
            keeper = documents[0]
            stale_ids = [
                document["_id"]
                for document in documents[1:]
                if document["_id"] != keeper["_id"]
            ]
            print(
                "  "
                f"doctor_id={group['_id']['doctor_id']} "
                f"start_at={group['_id']['start_at']} "
                f"count={group['count']} "
                f"keep={keeper['_id']} "
                f"delete={len(stale_ids)}"
            )
            if apply and stale_ids:
                result = await slots.delete_many(
                    {"_id": {"$in": stale_ids}}
                )
                deleted += result.deleted_count

        if not apply:
            print("Dry run only. Re-run with --apply to delete duplicates.")
            return 0

        print(f"Deleted {deleted} duplicate slots.")

        existing = await slots.index_information()
        for name, info in existing.items():
            if list(info.get("key", [])) == INDEX_KEY and name != INDEX_NAME:
                await slots.drop_index(name)
                print(f"Dropped equivalent index {name}.")

        await slots.create_index(
            INDEX_KEY,
            unique=True,
            name=INDEX_NAME,
        )
        print(f"Created unique index {INDEX_NAME}.")
        return 0
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="delete duplicate slots and create the unique index",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.apply)))


if __name__ == "__main__":
    main()
