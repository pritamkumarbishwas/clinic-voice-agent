from datetime import datetime, timezone
from typing import List, Optional
from time import perf_counter

from app.database import db
call_turns = db["call_turns"]

def now_ms() -> float:
    """Return a monotonic timestamp in milliseconds."""
    return perf_counter() * 1000

def new_turn(call_id: str) -> dict:
    return {
        "call_id": call_id,
        "started_at": datetime.now(timezone.utc),
        "speech_end_ms": None,
        "stt_final_ms": None,
        "llm_first_token_ms": None,
        "tts_first_audio_ms": None,
        "first_audio_heard_ms": None,
        "endpoint_latency_ms": None,
        "stt_latency_ms": None,
        "llm_latency_ms": None,
        "tts_latency_ms": None,
        "end_to_audio_ms": None,
        "timing_quality": "pending",
    }


async def save_turn(turn: dict):
    await call_turns.insert_one(turn)


async def initialize_analytics():
    await call_turns.create_index(
        [("call_id", 1), ("started_at", 1)]
    )
    await call_turns.create_index("started_at")