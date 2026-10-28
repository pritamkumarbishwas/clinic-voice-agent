"""Compatibility entry point for the LiveKit agent CLI.

The implementation lives in ``app.agent``. Existing imports such as
``import agent`` keep working, and ``python agent.py dev`` still discovers the
``AgentServer`` instance exported here.
"""

from livekit.plugins import silero

from app.agent.audio import (
    _build_tts,
    _close_tts,
    _session_connect_options,
)
from app.agent.constants import (
    AGENT_NAME,
    CONTROL_TOPIC,
    LLM_FALLBACK_PROMPT,
    LLM_MAX_RETRIES,
    STT_REPEAT_PROMPT,
    TRANSCRIPT_TOPIC,
    TTS_MAX_RETRIES,
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
from app.agent.worker import (
    _ensure_database,
    clinic_receptionist,
    prewarm,
    server,
)
from app.config import settings
from app.prompts.receptionist import (
    PROMPT_VERSION,
    SUPPORTED_LANGUAGES,
    build_greeting_instructions,
    build_system_prompt,
)
from app.services.booking_service import (
    book_appointment as db_book_appointment,
    check_availability as db_check_availability,
)
from app.services.knowledge_service import search_knowledge

__all__ = [
    "AGENT_NAME",
    "CONTROL_TOPIC",
    "ClinicReceptionist",
    "LLM_FALLBACK_PROMPT",
    "LLM_MAX_RETRIES",
    "PROMPT_VERSION",
    "STT_REPEAT_PROMPT",
    "SUPPORTED_LANGUAGES",
    "TRANSCRIPT_TOPIC",
    "TTS_MAX_RETRIES",
    "_build_tts",
    "_close_tts",
    "_config_snapshot",
    "_ensure_database",
    "_is_interrupt_request",
    "_is_llm_error",
    "_is_stt_error",
    "_is_timeout_error",
    "_is_tts_error",
    "_item_turn_id",
    "_milliseconds",
    "_run_id_from_job",
    "_session_connect_options",
    "_transcript_entry",
    "build_greeting_instructions",
    "build_system_prompt",
    "clinic_receptionist",
    "db_book_appointment",
    "db_check_availability",
    "prewarm",
    "search_knowledge",
    "server",
    "settings",
    "silero",
]
