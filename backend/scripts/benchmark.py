import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import (
    benchmark_runs,
    call_turns,
    calls,
    close_database,
    initialize_database,
)

TARGET_CALLS = 20


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "run")[:32]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage 20-call latency benchmark runs"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--label", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--run-id", required=True)

    finish = subparsers.add_parser("finish")
    finish.add_argument("--run-id", required=True)
    finish.add_argument("--notes", default="")

    return parser.parse_args()


async def start(args: argparse.Namespace) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    run_id = f"{slugify(args.label)}-{stamp}"

    await benchmark_runs.update_one(
        {"run_id": run_id},
        {
            "$setOnInsert": {
                "run_id": run_id,
                "label": args.label.strip(),
                "created_at": datetime.now(timezone.utc),
                "status": "collecting",
                "target_calls": TARGET_CALLS,
            }
        },
        upsert=True,
    )

    print(json.dumps({"run_id": run_id, "target_calls": TARGET_CALLS}))
    print(
        "\nOpen the Live call tab, enter this run id in "
        "'Test run label', and complete 20 scripted calls."
    )


async def status(args: argparse.Namespace) -> None:
    call_docs = await calls.find(
        {"run_id": args.run_id},
        {"_id": 0, "call_id": 1, "booking_outcome": 1, "barge_in_count": 1},
    ).to_list(length=1000)
    turn_count = await call_turns.count_documents(
        {"run_id": args.run_id}
    )
    booked = sum(
        1 for call in call_docs if call.get("booking_outcome") == "booked"
    )
    barge_ins = sum(
        int(call.get("barge_in_count") or 0) for call in call_docs
    )

    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "calls": len(call_docs),
                "target_calls": TARGET_CALLS,
                "remaining_calls": max(0, TARGET_CALLS - len(call_docs)),
                "turns": turn_count,
                "booked_calls": booked,
                "barge_ins": barge_ins,
            },
            indent=2,
        )
    )

    if len(call_docs) < TARGET_CALLS:
        print(
            f"\n{len(call_docs)}/{TARGET_CALLS} calls collected. "
            "Run the fixed 20-call script before reporting."
        )


async def finish(args: argparse.Namespace) -> None:
    result = await benchmark_runs.update_one(
        {"run_id": args.run_id},
        {
            "$set": {
                "status": "finished",
                "finished_at": datetime.now(timezone.utc),
                "notes": args.notes,
            }
        },
    )
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "updated": bool(result.matched_count),
            }
        )
    )


async def main() -> None:
    args = parse_args()
    await initialize_database()

    try:
        if args.command == "start":
            await start(args)
        elif args.command == "status":
            await status(args)
        elif args.command == "finish":
            await finish(args)
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
