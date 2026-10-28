import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from livekit import agents

from app.config import sanitize_run_id


def _milliseconds(value) -> float | None:
    if isinstance(value, (int, float)) and value >= 0:
        return round(float(value) * 1000, 2)
    return None


def _is_stt_error(error) -> bool:
    return getattr(error, "type", None) == "stt_error"


def _is_llm_error(error) -> bool:
    return getattr(error, "type", None) == "llm_error"


def _is_tts_error(error) -> bool:
    return getattr(error, "type", None) == "tts_error"


def _is_interrupt_request(packet) -> bool:
    if getattr(packet, "topic", None) != "control":
        return False

    try:
        payload = json.loads(packet.data.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return False

    return isinstance(payload, dict) and payload.get("type") == "interrupt"


def _is_timeout_error(error) -> bool:
    current = getattr(error, "error", error)
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (TimeoutError, asyncio.TimeoutError)):
            return True
        if "timeout" in type(current).__name__.lower():
            return True
        current = getattr(current, "__cause__", None) or getattr(
            current, "__context__", None
        )

    return False


def _transcript_entry(
    role: str, text: str, message_id: str | None = None
) -> dict:
    entry = {
        "role": role,
        "text": text,
        "timestamp": datetime.now(timezone.utc),
    }
    if message_id:
        entry["message_id"] = message_id
    return entry


def _item_turn_id(item) -> str:
    return item.id or f"turn-{uuid4().hex}"


def _run_id_from_job(ctx: agents.JobContext) -> str | None:
    raw = getattr(ctx.job, "metadata", "") or ""
    if not raw:
        return None

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return sanitize_run_id(raw)

    if not isinstance(payload, dict):
        return None
    return sanitize_run_id(payload.get("run_id"))
