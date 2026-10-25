import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import call_turns, calls, client
from app.services.latency_report import (
    LATENCY_FIELDS,
    build_markdown,
    build_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report per-stage voice latency for a benchmark run"
    )
    parser.add_argument(
        "--run-id",
        help="Only include calls tagged with this run id",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json", "both"),
        default="markdown",
    )
    parser.add_argument(
        "--output",
        help="Write report to this path (extension is added for 'both')",
    )
    parser.add_argument(
        "--title",
        default="Voice agent latency report",
    )
    return parser.parse_args()


async def build(args: argparse.Namespace) -> dict:
    turn_query = {"run_id": args.run_id} if args.run_id else {}
    call_query = {"run_id": args.run_id} if args.run_id else {}

    projection = {
        field: 1 for field in LATENCY_FIELDS
    } | {"_id": 0, "call_id": 1, "run_id": 1}

    turns = await call_turns.find(turn_query, projection).to_list(
        length=100000
    )
    call_docs = await calls.find(
        call_query,
        {
            "_id": 0,
            "call_id": 1,
            "booking_outcome": 1,
            "barge_in_count": 1,
        },
    ).to_list(length=100000)

    report = build_report(turns, call_docs)
    report["run_id"] = args.run_id
    return report


def render(report: dict, args: argparse.Namespace) -> None:
    markdown = build_markdown(report, args.title)
    payload = json.dumps(report, indent=2, default=str)

    if not args.output:
        if args.format == "json":
            print(payload)
        else:
            print(markdown)
        return

    if args.format == "both":
        markdown_path = Path(f"{args.output}.md")
        json_path = Path(f"{args.output}.json")
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        json_path.write_text(payload, encoding="utf-8")
        print(f"Wrote {markdown_path} and {json_path}")
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        payload if args.format == "json" else markdown,
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")


async def main() -> None:
    args = parse_args()
    try:
        report = await build(args)
        render(report, args)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
