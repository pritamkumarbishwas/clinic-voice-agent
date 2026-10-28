import asyncio
import logging

from livekit import agents
from livekit.agents import AgentServer
from livekit.plugins import silero

from app.agent.constants import AGENT_NAME
from app.agent.session import run_receptionist_session
from app.config import settings
from app.core.logging import configure_logging
from app.db.mongo import initialize_database

configure_logging("clinic-agent", settings.log_level)
logger = logging.getLogger("clinic-booking-agent")


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


@server.rtc_session(agent_name=AGENT_NAME)
async def clinic_receptionist(ctx: agents.JobContext):
    await _ensure_database()
    await run_receptionist_session(ctx)


if __name__ == "__main__":
    agents.cli.run_app(server)
