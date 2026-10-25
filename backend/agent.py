import asyncio
import contextlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    RunContext,
    function_tool,
)
from livekit.agents.llm import ChatMessage
from livekit.plugins import sarvam, silero

from app.database import call_turns, calls, initialize_database
from app.services.analytics_worker import process_call
from app.services.booking_service import (
    CLINIC_TZ,
    book_appointment as db_book_appointment,
    check_availability as db_check_availability,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clinic-booking-agent")

AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "clinic-receptionist")
TRANSCRIPT_TOPIC = "transcripts"
AVAILABILITY_TIMEOUT_SECONDS = 8.0
BOOKING_TIMEOUT_SECONDS = 10.0

server = AgentServer()

_db_ready = False
_db_lock = asyncio.Lock()


async def _ensure_database() -> None:
    """Index creation is process-wide work, not per-call work."""
    global _db_ready
    if _db_ready:
        return

    async with _db_lock:
        if not _db_ready:
            await initialize_database()
            _db_ready = True


SYSTEM_PROMPT = """
You are a polite AI clinic receptionist.
You must identify yourself as an AI receptionist when greeting the caller.

Today's date is {today} in the clinic timezone (Asia/Kolkata).
The clinic is open from 10:00 to 17:00 local time.

LANGUAGE
- Speak natural Indian Hinglish by default.
- Match the caller's Hindi or English preference.
- Keep responses short and ask one question at a time.

AVAILABILITY
- Use check_availability for real availability.
- Convert relative dates ("tomorrow", "parso") to YYYY-MM-DD before calling the tool.
- Never invent doctors, times, or available slots.
- Only offer slot IDs returned by the availability tool.
- Say times in the caller's local time, not UTC.

BOOKING SAFETY
- Collect the patient's name and phone number.
- Repeat the doctor, date, time, name and phone number for confirmation.
- Ask whether the caller wants you to book the appointment.
- Do not call book_appointment until the caller explicitly says yes.
- Pass confirmed=true only after explicit caller confirmation.
- Pass the exact slot_id returned by check_availability.
- If the slot is taken, apologise and check availability again.
- Only announce a booking as successful when the booking tool returns ok=true.
- Never claim an appointment is booked after a timeout or failed tool call.

MEDICAL SAFETY
- Never diagnose or prescribe medication.
- Refer medical questions to a qualified clinician.

INTERRUPTIONS
- If the caller interrupts you, stop the current response and listen.
- Respond to the caller's latest request instead of continuing the old reply.
- Do not treat background noise or silence as confirmation.

ERRORS
- If a tool fails, say:
  "Sorry, appointment system mein abhi problem aa rahi hai.
   Main booking confirm nahi kar pa raha hoon."
- Never invent a booking reference.

Keep every spoken response concise.
"""


def _milliseconds(value) -> float | None:
    if isinstance(value, (int, float)) and value >= 0:
        return round(float(value) * 1000, 2)
    return None


def _transcript_entry(role: str, text: str, message_id: str | None = None) -> dict:
    entry = {
        "role": role,
        "text": text,
        "timestamp": datetime.now(timezone.utc),
    }
    if message_id:
        entry["message_id"] = message_id
    return entry


class ClinicReceptionist(Agent):
    def __init__(self, call_id: str, today: str):
        super().__init__(instructions=SYSTEM_PROMPT.format(today=today))
        self.call_id = call_id

    @function_tool()
    async def check_availability(
        self,
        context: RunContext,
        date: str,
        doctor: str,
    ) -> str:
        """Check real available appointment slots.

        Args:
            date: Requested date in YYYY-MM-DD format.
            doctor: Doctor's name, for example Dr. Sharma.
        """
        try:
            result = await asyncio.wait_for(
                db_check_availability(date, doctor),
                timeout=AVAILABILITY_TIMEOUT_SECONDS,
            )
            return json.dumps(result, default=str)

        except Exception:
            logger.exception("Availability tool failed")
            return json.dumps(
                {
                    "ok": False,
                    "message": (
                        "Availability service is temporarily unavailable. "
                        "Tell the caller you cannot verify availability."
                    ),
                }
            )

    @function_tool()
    async def book_appointment(
        self,
        context: RunContext,
        name: str,
        phone: str,
        slot_id: str,
        confirmed: bool,
    ) -> str:
        """Book a slot only after the caller explicitly confirms.

        Args:
            name: Patient's full name.
            phone: Patient's phone number.
            slot_id: Exact slot_id returned by check_availability.
            confirmed: True only after the caller explicitly agrees
                to book the repeated appointment details.
        """
        if confirmed is not True:
            return json.dumps(
                {
                    "ok": False,
                    "message": (
                        "Booking not attempted. Confirm the appointment "
                        "details with the caller first."
                    ),
                }
            )

        try:
            result = await asyncio.wait_for(
                db_book_appointment(
                    name=name,
                    phone=phone,
                    slot_id=slot_id,
                    call_id=self.call_id,
                ),
                timeout=BOOKING_TIMEOUT_SECONDS,
            )
            return json.dumps(result, default=str)

        except Exception:
            logger.exception("Booking tool failed")
            return json.dumps(
                {
                    "ok": False,
                    "code": "BOOKING_ERROR",
                    "message": (
                        "Booking could not be verified. Do not claim "
                        "success. Check the booking state before retrying."
                    ),
                }
            )


@server.rtc_session(agent_name=AGENT_NAME)
async def clinic_receptionist(ctx: agents.JobContext):
    await ctx.connect()
    await _ensure_database()

    call_id = str(uuid4())
    today = datetime.now(CLINIC_TZ).date().isoformat()

    await calls.insert_one(
        {
            "call_id": call_id,
            "room_name": ctx.room.name,
            "started_at": datetime.now(timezone.utc),
            "ended_at": None,
            "transcript": [],
            "booking_outcome": "not_booked",
            "appointment_id": None,
            "analysis_status": "pending",
        }
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=sarvam.STTRealtime(
            language="hi-IN",
            stream_type="balanced",
            mode="codemix",
        ),
        llm=sarvam.LLM(model="sarvam-105b"),
        tts=sarvam.TTS(
            target_language_code="hi-IN",
            model="bulbul:v3",
            speaker="shubh",
            pace=1.0,
            min_buffer_size=50,
            max_chunk_length=150,
        ),
    )

    # All transcript/metric writes go through one ordered queue, so a turn is
    # always inserted before its reply updates it (no races between events).
    jobs: asyncio.Queue[tuple] = asyncio.Queue()
    pending_turns: list = []
    persisted_message_ids: set[str] = set()

    async def publish_transcript(role: str, text: str, is_final: bool) -> None:
        try:
            payload = {
                "type": "transcript",
                "role": role,
                "text": text,
                "isFinal": is_final,
                "receivedAt": round(time.time() * 1000),
            }
            await ctx.room.local_participant.publish_data(
                json.dumps(payload).encode("utf-8"),
                reliable=True,
                topic=TRANSCRIPT_TOPIC,
            )
        except Exception:
            logger.exception("Could not publish transcript")
            return

    async def handle_item(item: ChatMessage, metrics: dict) -> None:
        text = (item.text_content or "").strip()

        if item.role == "user":
            result = await call_turns.insert_one(
                {
                    "call_id": call_id,
                    "turn_id": item.id,
                    "role": "user",
                    "started_at": datetime.now(timezone.utc),
                    "endpoint_latency_ms": _milliseconds(
                        metrics.get("end_of_turn_delay")
                    ),
                    "stt_latency_ms": _milliseconds(
                        metrics.get("transcription_delay")
                    ),
                    "llm_latency_ms": None,
                    "tts_latency_ms": None,
                    "end_to_audio_ms": None,
                    "playback_latency_ms": None,
                    "assistant_interrupted": False,
                    "timing_quality": "livekit_per_turn",
                }
            )
            pending_turns.append(result.inserted_id)
            return

        if text and item.id and item.id not in persisted_message_ids:
            persisted_message_ids.add(item.id)
            await calls.update_one(
                {"call_id": call_id},
                {
                    "$push": {
                        "transcript": _transcript_entry(
                            "assistant", text, item.id
                        )
                    }
                },
            )
            await publish_transcript("assistant", text, True)

        metrics_update = {
            "llm_latency_ms": _milliseconds(metrics.get("llm_node_ttft")),
            "tts_latency_ms": _milliseconds(metrics.get("tts_node_ttfb")),
            "end_to_audio_ms": _milliseconds(metrics.get("e2e_latency")),
            "playback_latency_ms": _milliseconds(metrics.get("playback_latency")),
            "assistant_interrupted": bool(item.interrupted),
        }
        has_timing = any(
            value is not None
            for key, value in metrics_update.items()
            if key != "assistant_interrupted"
        )

        if pending_turns:
            await call_turns.update_one(
                {"_id": pending_turns.pop(0)},
                {"$set": metrics_update},
            )
        elif has_timing or item.interrupted:
            await call_turns.insert_one(
                {
                    "call_id": call_id,
                    "turn_id": item.id,
                    "role": "assistant",
                    "started_at": datetime.now(timezone.utc),
                    **metrics_update,
                }
            )

    async def persist_worker() -> None:
        while True:
            job = await jobs.get()
            try:
                if job[0] == "item":
                    await handle_item(job[1], job[2])
                elif job[0] == "transcript":
                    await calls.update_one(
                        {"call_id": call_id},
                        {
                            "$push": {
                                "transcript": _transcript_entry("user", job[1])
                            }
                        },
                    )
            except Exception:
                logger.exception("Failed to persist %s for %s", job[0], call_id)
            finally:
                jobs.task_done()

    worker_task = asyncio.create_task(
        persist_worker(), name=f"persist-{call_id}"
    )

    @session.on("conversation_item_added")
    def on_conversation_item_added(event):
        item = event.item
        if isinstance(item, ChatMessage):
            jobs.put_nowait(("item", item, dict(item.metrics or {})))

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        text = (event.transcript or "").strip()
        if not text:
            return

        if event.is_final:
            jobs.put_nowait(("transcript", text))

        asyncio.create_task(
            publish_transcript("user", text, bool(event.is_final))
        )

    async def finalize(_reason: str) -> None:
        with contextlib.suppress(Exception):
            await jobs.join()

        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task

        try:
            await calls.update_one(
                {"call_id": call_id},
                {"$set": {"ended_at": datetime.now(timezone.utc)}},
            )
        except Exception:
            logger.exception("Could not save call end time")

        try:
            await process_call(call_id)
        except Exception:
            logger.exception("Call analysis failed: %s", call_id)
            await calls.update_one(
                {"call_id": call_id},
                {"$set": {"analysis_status": "failed"}},
            )

    ctx.add_shutdown_callback(finalize)

    try:
        await session.start(
            room=ctx.room,
            agent=ClinicReceptionist(call_id, today),
        )
        logger.info("Clinic booking agent started: %s", call_id)

        await session.generate_reply(
            instructions=(
                "Greet the caller in natural Hinglish. "
                "Introduce yourself as an AI clinic receptionist "
                "and ask how you can help."
            )
        )
    except Exception:
        logger.exception("Clinic agent session failed")
        ctx.shutdown("agent session failed")


if __name__ == "__main__":
    agents.cli.run_app(server)
