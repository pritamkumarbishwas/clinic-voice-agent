import os
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,47}$")
DEFAULT_SARVAM_BASE_URL = "https://api.sarvam.ai/v2"
SARVAM_V1_MODELS = {"sarvam-105b-conversations"}


def _text(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def sanitize_run_id(value: str | None) -> str | None:
    """Keep run identifiers safe for dispatch metadata and reporting."""
    if not isinstance(value, str):
        return None

    cleaned = " ".join(value.split())
    if not cleaned or not RUN_ID_PATTERN.fullmatch(cleaned):
        return None
    return cleaned


@dataclass(frozen=True)
class Settings:
    livekit_agent_name: str
    clinic_timezone: ZoneInfo

    stt_language: str
    stt_stream_type: str
    stt_mode: str
    stt_endpointing: str

    llm_model: str

    tts_language: str
    tts_model: str
    tts_speaker: str
    tts_pace: float
    tts_min_buffer_size: int
    tts_max_chunk_length: int

    min_endpointing_delay: float
    max_endpointing_delay: float
    interruption_min_duration: float
    preemptive_tts: bool

    analysis_model: str
    analysis_max_attempts: int
    analysis_poll_seconds: float
    analysis_timeout_seconds: float
    analysis_worker_enabled: bool
    analysis_transcript_chars: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            livekit_agent_name=_text(
                "LIVEKIT_AGENT_NAME", "clinic-receptionist"
            ),
            clinic_timezone=ZoneInfo(
                _text("CLINIC_TIMEZONE", "Asia/Kolkata")
            ),
            stt_language=_text("STT_LANGUAGE", "hi-IN"),
            stt_stream_type=_text("STT_STREAM_TYPE", "balanced"),
            stt_mode=_text("STT_MODE", "codemix"),
            stt_endpointing=_text("STT_ENDPOINTING", "vad"),
            llm_model=_text("LLM_MODEL", "sarvam-105b"),
            tts_language=_text("TTS_LANGUAGE", "hi-IN"),
            tts_model=_text("TTS_MODEL", "bulbul:v3"),
            tts_speaker=_text("TTS_SPEAKER", "shubh"),
            tts_pace=_float("TTS_PACE", 1.0),
            tts_min_buffer_size=_int("TTS_MIN_BUFFER_SIZE", 50),
            tts_max_chunk_length=_int("TTS_MAX_CHUNK_LENGTH", 150),
            min_endpointing_delay=_float("MIN_ENDPOINTING_DELAY", 0.5),
            max_endpointing_delay=_float("MAX_ENDPOINTING_DELAY", 3.0),
            interruption_min_duration=_float(
                "INTERRUPTION_MIN_DURATION", 0.5
            ),
            preemptive_tts=_bool("PREEMPTIVE_TTS", False),
            analysis_model=_text("ANALYSIS_MODEL", "sarvam-105b"),
            analysis_max_attempts=_int("ANALYSIS_MAX_ATTEMPTS", 3),
            analysis_poll_seconds=_float("ANALYSIS_POLL_SECONDS", 2.0),
            analysis_timeout_seconds=_float(
                "ANALYSIS_TIMEOUT_SECONDS", 20.0
            ),
            analysis_worker_enabled=_bool(
                "ANALYSIS_WORKER_ENABLED", True
            ),
            analysis_transcript_chars=_int(
                "ANALYSIS_TRANSCRIPT_CHARS", 6000
            ),
        )

    @property
    def sarvam_llm_base_url(self) -> str:
        if self.analysis_model in SARVAM_V1_MODELS:
            return "https://api.sarvam.ai/v1"
        return _text("SARVAM_LLM_BASE_URL", DEFAULT_SARVAM_BASE_URL)


settings = Settings.from_env()
