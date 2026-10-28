import asyncio
import contextlib
import json
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from livekit import agents
from livekit.agents import AgentSession
from livekit.agents.llm import ChatMessage
from livekit.plugins import sarvam

from app.agent.audio import (
    _build_tts,
    _close_tts,
    _session_connect_options,
)
from app.agent.constants import (
    LLM_FALLBACK_PROMPT,
    STT_REPEAT_PROMPT,
    TRANSCRIPT_TOPIC,
)
from app.agent.helpers import (
    _is_interrupt_request,
    _is_llm_error,
    _is_stt_error,
    _is_timeout_error,
    _is_tts_error,
    _item_turn_id,
    _milliseconds,
    _run_id_from_job,
    _transcript_entry,
)
from app.agent.receptionist import ClinicReceptionist
from app.agent.telemetry import _config_snapshot
from app.config import settings
from app.db.mongo import call_turns, calls
from app.prompts.receptionist import build_greeting_instructions
from app.services.booking_service import (
    CLINIC_TZ,
    format_doctor_roster,
    format_stt_prompt,
    get_doctor_directory,
)
from app.services.clinic_service import (
    DEFAULT_CLINIC,
    format_clinic_for_prompt,
    get_clinic_profile,
)

logger = logging.getLogger("clinic-booking-agent")


def _enqueue(queue: asyncio.Queue, item: tuple) -> None:
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        logger.warning(
            "Agent persistence queue is full; dropping %s", item[0]
        )


async def run_receptionist_session(ctx: agents.JobContext) -> None:
    await ctx.connect()

    call_id = str(uuid4())
    run_id = _run_id_from_job(ctx)
    today = datetime.now(CLINIC_TZ).date().isoformat()

    try:
        clinic_profile = await get_clinic_profile()
    except Exception:
        logger.exception("Could not load clinic profile")
        clinic_profile = DEFAULT_CLINIC.model_dump()
    clinic_name = str(clinic_profile.get("name") or "")
    clinic_details = format_clinic_for_prompt(clinic_profile, today=today)

    try:
        doctor_docs = await get_doctor_directory()
    except Exception:
        logger.exception("Could not load doctor roster")
        doctor_docs = []
    doctor_roster = format_doctor_roster(doctor_docs)
    stt_prompt = format_stt_prompt(doctor_docs)

    try:
        tts_impl = _build_tts()
    except Exception:
        logger.exception("Could not initialize TTS")
        ctx.shutdown("tts unavailable")
        return

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
                "stt_error_count": 0,
                "stt_timeout_count": 0,
                "empty_transcript_count": 0,
                "llm_error_count": 0,
                "tts_error_count": 0,
                "booking_outcome": "not_booked",
                "appointment_id": None,
                "analysis_status": "pending",
                "analysis_attempts": 0,
                "analysis_locked_at": None,
                "agent_config": _config_snapshot(),
            }
        )
    except Exception:
        logger.exception(
            "Could not create the call record for %s", ctx.room.name
        )
        await _close_tts(tts_impl)
        ctx.shutdown("database unavailable")
        return

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        transcription_timeout=settings.stt_transcription_timeout,
        conn_options=_session_connect_options(),
        stt=sarvam.STTRealtime(
            language=settings.stt_language,
            stream_type=settings.stt_stream_type,
            mode=settings.stt_mode,
            endpointing=settings.stt_endpointing,
            prompt=stt_prompt,
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
        llm=sarvam.LLM(
            model=settings.llm_model,
            timeout=httpx.Timeout(settings.llm_timeout_seconds),
            max_tokens=settings.llm_max_tokens,
            api_key=settings.sarvam_api_key,
        ),
        tts=tts_impl,
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

    jobs: asyncio.Queue[tuple] = asyncio.Queue(
        maxsize=settings.agent_queue_max_size
    )
    publish_jobs: asyncio.Queue[tuple[str, str, bool]] = asyncio.Queue(
        maxsize=settings.agent_queue_max_size
    )
    speech_handles: list = []
    last_user_item_id: str | None = None
    persisted_message_ids: set[str] = set()
    stt_error_count = 0
    stt_timeout_count = 0
    empty_transcript_count = 0
    llm_error_count = 0
    tts_error_count = 0
    llm_fallback_task: asyncio.Task | None = None
    interrupt_tasks: set[asyncio.Task] = set()
    last_repeat_prompt_at = 0.0

    def prompt_repeat() -> None:
        """Ask once for a repeat without racing a new caller turn."""
        nonlocal last_repeat_prompt_at
        now = time.monotonic()
        if (
            now - last_repeat_prompt_at
            < settings.stt_repeat_cooldown_seconds
        ):
            return
        if (
            session.agent_state == "speaking"
            or session.user_state == "speaking"
        ):
            return

        last_repeat_prompt_at = now
        with contextlib.suppress(Exception):
            session.say(STT_REPEAT_PROMPT, allow_interruptions=True)

    async def speak_llm_fallback_when_ready() -> None:
        while session.user_state == "speaking":
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.5)

        if (
            session.user_state == "speaking"
            or session.agent_state in ("thinking", "speaking")
            or session.current_speech is not None
        ):
            return

        try:
            session.say(LLM_FALLBACK_PROMPT, allow_interruptions=True)
        except Exception:
            logger.exception("Could not speak the LLM fallback")

    def prompt_llm_fallback() -> None:
        """Speak a short fallback when the LLM fails or times out."""
        nonlocal llm_fallback_task
        if session.agent_state == "speaking":
            return

        if session.user_state == "speaking":
            if (
                llm_fallback_task is not None
                and not llm_fallback_task.done()
            ):
                return
            try:
                llm_fallback_task = asyncio.create_task(
                    speak_llm_fallback_when_ready()
                )
            except RuntimeError:
                logger.exception("Could not schedule the LLM fallback")
            return

        if llm_fallback_task is not None and not llm_fallback_task.done():
            llm_fallback_task.cancel()

        try:
            session.say(LLM_FALLBACK_PROMPT, allow_interruptions=True)
        except Exception:
            logger.exception("Could not speak the LLM fallback")

    async def publish_transcript(
        role: str, text: str, is_final: bool
    ) -> None:
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
            _enqueue(publish_jobs, ("assistant", text, True))

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
                                "transcript": _transcript_entry(
                                    "user", job[1]
                                )
                            }
                        },
                    )
                elif job[0] == "tools":
                    await calls.update_one(
                        {"call_id": call_id},
                        {"$push": {"tool_calls": {"$each": job[1]}}},
                    )
                elif job[0] in (
                    "stt_failure",
                    "llm_failure",
                    "tts_failure",
                ):
                    await calls.update_one(
                        {"call_id": call_id},
                        {"$inc": {job[1]: 1}},
                    )
            except Exception:
                logger.exception(
                    "Failed to persist %s for %s", job[0], call_id
                )
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

    async def enforce_max_duration() -> None:
        await asyncio.sleep(settings.call_max_duration_seconds)
        logger.warning("Call %s exceeded maximum duration", call_id)
        ctx.shutdown("maximum call duration reached")

    max_duration_task = asyncio.create_task(
        enforce_max_duration(), name=f"max-duration-{call_id}"
    )

    @session.on("conversation_item_added")
    def on_conversation_item_added(event):
        item = event.item
        if isinstance(item, ChatMessage):
            _enqueue(
                jobs, ("item", item, dict(item.metrics or {}))
            )

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
            _enqueue(jobs, ("tools", entries))

    @session.on("speech_created")
    def on_speech_created(event):
        speech_handles.append(event.speech_handle)

    async def interrupt_speech() -> None:
        try:
            await session.interrupt(force=True)
            logger.info(
                "Caller stopped receptionist speech on call %s", call_id
            )
        except RuntimeError:
            logger.debug(
                "No receptionist speech to interrupt on call %s", call_id
            )
        except Exception:
            logger.exception("Could not interrupt receptionist speech")

    def on_data_received(packet) -> None:
        if not _is_interrupt_request(packet):
            return

        task = asyncio.create_task(interrupt_speech())
        interrupt_tasks.add(task)
        task.add_done_callback(interrupt_tasks.discard)

    ctx.room.on("data_received", on_data_received)

    @session.on("error")
    def on_session_error(event):
        nonlocal stt_error_count, llm_error_count, tts_error_count
        error = getattr(event, "error", None)

        if _is_stt_error(error):
            stt_error_count += 1
            _enqueue(jobs, ("stt_failure", "stt_error_count"))
            logger.warning("STT error on call %s: %s", call_id, error)
            return

        if _is_tts_error(error):
            tts_error_count += 1
            _enqueue(jobs, ("tts_failure", "tts_error_count"))
            reason = (
                "timeout" if _is_timeout_error(error) else "error"
            )
            recoverable = bool(getattr(error, "recoverable", False))
            logger.warning(
                "TTS %s on call %s (recoverable=%s): %s",
                reason,
                call_id,
                recoverable,
                error,
            )
            return

        if _is_llm_error(error):
            llm_error_count += 1
            _enqueue(jobs, ("llm_failure", "llm_error_count"))
            reason = (
                "timeout" if _is_timeout_error(error) else "error"
            )
            recoverable = bool(getattr(error, "recoverable", False))
            logger.warning(
                "LLM %s on call %s (recoverable=%s): %s",
                reason,
                call_id,
                recoverable,
                error,
            )
            if not recoverable:
                prompt_llm_fallback()

    @session.on("user_transcription_timeout")
    def on_user_transcription_timeout(event):
        nonlocal stt_timeout_count
        stt_timeout_count += 1
        _enqueue(jobs, ("stt_failure", "stt_timeout_count"))
        logger.info(
            "STT timeout on call %s after %.2fs of speech",
            call_id,
            getattr(event, "speech_duration", 0.0),
        )
        prompt_repeat()

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        nonlocal empty_transcript_count, last_repeat_prompt_at
        text = (event.transcript or "").strip()
        if not text:
            if event.is_final:
                empty_transcript_count += 1
                _enqueue(
                    jobs, ("stt_failure", "empty_transcript_count")
                )
                prompt_repeat()
            return

        if event.is_final:
            last_repeat_prompt_at = 0.0
            _enqueue(jobs, ("transcript", text))

        _enqueue(publish_jobs, ("user", text, bool(event.is_final)))

    async def finalize(_reason: str) -> None:
        with contextlib.suppress(Exception):
            ctx.room.off("data_received", on_data_received)

        if llm_fallback_task is not None:
            llm_fallback_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await llm_fallback_task

        max_duration_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await max_duration_task

        for task in tuple(interrupt_tasks):
            task.cancel()
        for task in tuple(interrupt_tasks):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

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

        with contextlib.suppress(Exception):
            await asyncio.wait_for(_close_tts(tts_impl), timeout=5)

        logger.info(
            "Call %s ended (barge-ins=%s, speech turns=%s, "
            "stt errors=%s, stt timeouts=%s, empty transcripts=%s, "
            "llm errors=%s, tts errors=%s)",
            call_id,
            barge_in_count,
            len(speech_handles),
            stt_error_count,
            stt_timeout_count,
            empty_transcript_count,
            llm_error_count,
            tts_error_count,
        )

    ctx.add_shutdown_callback(finalize)

    try:
        await session.start(
            room=ctx.room,
            agent=ClinicReceptionist(
                call_id,
                today,
                clinic_name,
                clinic_details,
                doctor_roster,
            ),
        )
    except Exception:
        logger.exception("Clinic agent session failed")
        ctx.shutdown("agent session failed")
        return

    logger.info("Clinic booking agent started: %s", call_id)

    try:
        await session.generate_reply(
            instructions=build_greeting_instructions(clinic_name)
        )
    except Exception:
        logger.exception("Initial LLM greeting failed")
        prompt_llm_fallback()
