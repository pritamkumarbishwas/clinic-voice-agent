import asyncio
import contextlib
import json
import logging
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

from app.config import sanitize_run_id, settings
from app.database import call_turns, calls, initialize_database
from app.services.booking_service import (
    CLINIC_TZ,
    book_appointment as db_book_appointment,
    check_availability as db_check_availability,
)
from app.services.clinic_service import (
    DEFAULT_CLINIC,
    format_clinic_for_prompt,
    get_clinic_profile,
)

load_dotenv()

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO)
)
logger = logging.getLogger("clinic-booking-agent")

AGENT_NAME = settings.livekit_agent_name
TRANSCRIPT_TOPIC = "transcripts"
AVAILABILITY_TIMEOUT_SECONDS = 8.0
BOOKING_TIMEOUT_SECONDS = 10.0

def prewarm(proc) -> None:
    """Validate configuration and load the VAD once per worker process."""
    settings.validate()
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=settings.vad_min_speech_duration,
        min_silence_duration=settings.vad_min_silence_duration,
        prefix_padding_duration=settings.vad_prefix_padding_duration,
        activation_threshold=settings.vad_activation_threshold,
        deactivation_threshold=settings.vad_deactivation_threshold,
    )


server = AgentServer(setup_fnc=prewarm)

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

Today's date is {today} in the clinic timezone ({timezone}).

CLINIC INFORMATION
{clinic_details}

FAQ RULES
- Answer questions about timings, location, phone number, and consultation fees using only the clinic information above.
- If a detail is marked "Not configured" or is missing, say clinic staff will confirm it.
- Never invent an address, phone number, fee, or opening time.

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


def _config_snapshot() -> dict:
    return {
        "stt": {
            "language": settings.stt_language,
            "stream_type": settings.stt_stream_type,
            "mode": settings.stt_mode,
            "endpointing": settings.stt_endpointing,
        },
        "llm": {"model": settings.llm_model},
        "tts": {
            "language": settings.tts_language,
            "model": settings.tts_model,
            "speaker": settings.tts_speaker,
            "pace": settings.tts_pace,
            "min_buffer_size": settings.tts_min_buffer_size,
            "max_chunk_length": settings.tts_max_chunk_length,
        },
        "vad": {
            "min_speech_duration": settings.vad_min_speech_duration,
            "min_silence_duration": settings.vad_min_silence_duration,
            "prefix_padding_duration": settings.vad_prefix_padding_duration,
            "activation_threshold": settings.vad_activation_threshold,
            "deactivation_threshold": settings.vad_deactivation_threshold,
        },
        "turn_handling": {
            "turn_detection": "auto",
            "min_endpointing_delay": settings.min_endpointing_delay,
            "max_endpointing_delay": settings.max_endpointing_delay,
            "interruption_min_duration": settings.interruption_min_duration,
            "preemptive_tts": settings.preemptive_tts,
        },
    }


class ClinicReceptionist(Agent):
    def __init__(
        self,
        call_id: str,
        today: str,
        clinic_details: str,
    ):
        super().__init__(
            instructions=SYSTEM_PROMPT.format(
                today=today,
                timezone=CLINIC_TZ.key,
                clinic_details=clinic_details,
            )
        )
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
    await _ensure_database()
    await ctx.connect()

    call_id = str(uuid4())
    run_id = _run_id_from_job(ctx)
    today = datetime.now(CLINIC_TZ).date().isoformat()

    try:
        clinic_profile = await get_clinic_profile()
    except Exception:
        logger.exception("Could not load clinic profile")
        clinic_profile = DEFAULT_CLINIC.model_dump()
    clinic_details = format_clinic_for_prompt(clinic_profile)

    try:
        await calls.insert_one(
            {
                "call_id": call_id,
                "room_name": ctx.room.name,
                "run_id": run_id,
                "started_at": datetime.now(timezone.utc),
                "ended_at": None,
                "transcript": [],
                "tool_calls": [],
                "barge_in_count": 0,
                "speech_count": 0,
                "booking_outcome": "not_booked",
                "appointment_id": None,
                "analysis_status": "pending",
                "analysis_attempts": 0,
                "analysis_locked_at": None,
                "agent_config": _config_snapshot(),
            }
        )
    except Exception:
        logger.exception("Could not create the call record for %s", ctx.room.name)
        ctx.shutdown("database unavailable")
        return

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=sarvam.STTRealtime(
            language=settings.stt_language,
            stream_type=settings.stt_stream_type,
            mode=settings.stt_mode,
            endpointing=settings.stt_endpointing,
            vad_sot_threshold=settings.vad_activation_threshold,
            vad_min_speech_ms=round(
                settings.vad_min_speech_duration * 1000
            ),
            vad_min_silence_ms=round(
                settings.vad_min_silence_duration * 1000
            ),
            vad_prefix_padding_ms=round(
                settings.vad_prefix_padding_duration * 1000
            ),
        ),
        llm=sarvam.LLM(model=settings.llm_model),
        tts=sarvam.TTS(
            target_language_code=settings.tts_language,
            model=settings.tts_model,
            speaker=settings.tts_speaker,
            pace=settings.tts_pace,
            min_buffer_size=settings.tts_min_buffer_size,
            max_chunk_length=settings.tts_max_chunk_length,
        ),
        turn_handling={
            "endpointing": {
                "mode": "fixed",
                "min_delay": settings.min_endpointing_delay,
                "max_delay": settings.max_endpointing_delay,
            },
            "interruption": {
                "enabled": True,
                "min_duration": settings.interruption_min_duration,
                "min_words": 0,
                "resume_false_interruption": True,
            },
            "preemptive_generation": {
                "enabled": True,
                "preemptive_tts": settings.preemptive_tts,
            },
        },
    )

    # All transcript/metric writes go through one ordered queue, so a turn is
    # always inserted before its reply updates it (no races between events).
    jobs: asyncio.Queue[tuple] = asyncio.Queue()
    publish_jobs: asyncio.Queue[tuple[str, str, bool]] = asyncio.Queue()
    speech_handles: list = []
    last_user_item_id: str | None = None
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
        nonlocal last_user_item_id
        text = (item.text_content or "").strip()
        turn_id = _item_turn_id(item)

        if item.role == "user":
            last_user_item_id = turn_id
            await call_turns.update_one(
                {"call_id": call_id, "turn_id": turn_id},
                {
                    "$set": {
                        "run_id": run_id,
                        "endpoint_latency_ms": _milliseconds(
                            metrics.get("end_of_turn_delay")
                        ),
                        "stt_latency_ms": _milliseconds(
                            metrics.get("transcription_delay")
                        ),
                    },
                    "$setOnInsert": {
                        "role": "user",
                        "started_at": datetime.now(timezone.utc),
                        "llm_latency_ms": None,
                        "tts_latency_ms": None,
                        "end_to_audio_ms": None,
                        "playback_latency_ms": None,
                        "assistant_interrupted": False,
                        "timing_quality": "livekit_per_turn",
                    },
                },
                upsert=True,
            )
            return

        if text and turn_id not in persisted_message_ids:
            persisted_message_ids.add(turn_id)
            await calls.update_one(
                {"call_id": call_id},
                {
                    "$push": {
                        "transcript": _transcript_entry(
                            "assistant", text, turn_id
                        )
                    }
                },
            )
            publish_jobs.put_nowait(("assistant", text, True))

        # Keep the reply as its own row so each side's latency stays truthful:
        # caller rows carry endpoint/STT, assistant rows carry LLM/TTS/E2E.
        await call_turns.update_one(
            {"call_id": call_id, "turn_id": turn_id},
            {
                "$set": {
                    "run_id": run_id,
                    "llm_latency_ms": _milliseconds(
                        metrics.get("llm_node_ttft")
                    ),
                    "tts_latency_ms": _milliseconds(
                        metrics.get("tts_node_ttfb")
                    ),
                    "end_to_audio_ms": _milliseconds(
                        metrics.get("e2e_latency")
                    ),
                    "playback_latency_ms": _milliseconds(
                        metrics.get("playback_latency")
                    ),
                    "assistant_interrupted": bool(item.interrupted),
                },
                "$setOnInsert": {
                    "role": "assistant",
                    "started_at": datetime.now(timezone.utc),
                    "endpoint_latency_ms": None,
                    "stt_latency_ms": None,
                    "reply_to_turn_id": last_user_item_id,
                    "timing_quality": "livekit_per_turn",
                },
            },
            upsert=True,
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
                elif job[0] == "tools":
                    await calls.update_one(
                        {"call_id": call_id},
                        {"$push": {"tool_calls": {"$each": job[1]}}},
                    )
            except Exception:
                logger.exception("Failed to persist %s for %s", job[0], call_id)
            finally:
                jobs.task_done()

    async def publish_worker() -> None:
        while True:
            role, text, is_final = await publish_jobs.get()
            try:
                await publish_transcript(role, text, is_final)
            finally:
                publish_jobs.task_done()

    worker_task = asyncio.create_task(
        persist_worker(), name=f"persist-{call_id}"
    )
    publish_task = asyncio.create_task(
        publish_worker(), name=f"publish-{call_id}"
    )

    @session.on("conversation_item_added")
    def on_conversation_item_added(event):
        item = event.item
        if isinstance(item, ChatMessage):
            jobs.put_nowait(("item", item, dict(item.metrics or {})))

    @session.on("function_tools_executed")
    def on_function_tools_executed(event):
        timestamp = datetime.now(timezone.utc)
        entries = [
            {
                "call_id": call.call_id,
                "name": call.name,
                "arguments": call.arguments,
                "output": output.output,
                "is_error": bool(output.is_error),
                "timestamp": timestamp,
            }
            for call, output in event.zipped()
        ]
        if entries:
            jobs.put_nowait(("tools", entries))

    @session.on("speech_created")
    def on_speech_created(event):
        speech_handles.append(event.speech_handle)

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        text = (event.transcript or "").strip()
        if not text:
            return

        if event.is_final:
            jobs.put_nowait(("transcript", text))

        publish_jobs.put_nowait(("user", text, bool(event.is_final)))

    async def finalize(_reason: str) -> None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(jobs.join(), timeout=5)
            await asyncio.wait_for(publish_jobs.join(), timeout=5)

        worker_task.cancel()
        publish_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
        with contextlib.suppress(asyncio.CancelledError):
            await publish_task

        barge_in_count = sum(
            1 for handle in speech_handles if handle.interrupted
        )

        try:
            await calls.update_one(
                {"call_id": call_id},
                {
                    "$set": {
                        "ended_at": datetime.now(timezone.utc),
                        "barge_in_count": barge_in_count,
                        "speech_count": len(speech_handles),
                        "analysis_status": "pending",
                        "analysis_locked_at": None,
                    }
                },
            )
        except Exception:
            logger.exception("Could not save call end state")

        logger.info(
            "Call %s ended (barge-ins=%s, speech turns=%s)",
            call_id,
            barge_in_count,
            len(speech_handles),
        )

    ctx.add_shutdown_callback(finalize)

    try:
        await session.start(
            room=ctx.room,
            agent=ClinicReceptionist(call_id, today, clinic_details),
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
