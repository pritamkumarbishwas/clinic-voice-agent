import logging
import os
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("clinic-config")

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,47}$")
DEFAULT_SARVAM_BASE_URL = "https://api.sarvam.ai/v2"
SARVAM_V1_MODELS = {"sarvam-105b-conversations"}

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
COOKIE_SAMESITE_VALUES = {"lax", "strict", "none"}
JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}
LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
MIN_TURN_DETECTOR_VAD_SILENCE = 0.25
TTS_SAMPLE_RATES = {8000, 16000, 22050, 24000, 32000, 44100, 48000}


def _text(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid %s=%r; using default %s", name, raw, default
        )
        return default


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid %s=%r; using default %s", name, raw, default
        )
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    logger.warning(
        "Invalid %s=%r; using default %s", name, raw, default
    )
    return default


def _timezone(name: str, default: str) -> ZoneInfo:
    value = _text(name, default)
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Unknown timezone %s=%r; using default %s", name, value, default
        )
        return ZoneInfo(default)


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
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str

    sarvam_api_key: str
    mongodb_uri: str
    mongodb_database: str

    clinic_timezone: ZoneInfo

    stt_language: str
    stt_stream_type: str
    stt_mode: str
    stt_endpointing: str
    stt_transcription_timeout: float

    llm_model: str
    llm_timeout_seconds: float
    llm_max_tokens: int

    tts_language: str
    tts_model: str
    tts_speaker: str
    tts_pace: float
    tts_sample_rate: int
    tts_timeout_seconds: float
    tts_min_buffer_size: int
    tts_max_chunk_length: int

    vad_min_speech_duration: float
    vad_min_silence_duration: float
    vad_prefix_padding_duration: float
    vad_activation_threshold: float
    vad_deactivation_threshold: float

    min_endpointing_delay: float
    max_endpointing_delay: float
    interruption_min_duration: float
    preemptive_tts: bool
    session_max_unrecoverable_errors: int

    analysis_model: str
    analysis_max_attempts: int
    analysis_poll_seconds: float
    analysis_timeout_seconds: float
    analysis_worker_enabled: bool
    analysis_transcript_chars: int

    openai_api_key: str
    rag_enabled: bool
    openai_embedding_model: str
    rag_top_k: int
    rag_min_score: float
    rag_chunk_chars: int
    rag_chunk_overlap: int
    rag_timeout_seconds: float
    rag_max_upload_bytes: int
    rag_max_pdf_pages: int

    jwt_secret: str
    jwt_algorithm: str
    jwt_expire_minutes: int
    auth_cookie_name: str
    cookie_secure: bool
    cookie_samesite: str

    log_level: str
    sentry_dsn: str
    sentry_environment: str
    rate_limit_enabled: bool
    trust_proxy_headers: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            livekit_agent_name=_text(
                "LIVEKIT_AGENT_NAME", "clinic-receptionist"
            ),
            livekit_url=_text("LIVEKIT_URL", ""),
            livekit_api_key=_text("LIVEKIT_API_KEY", ""),
            livekit_api_secret=_text("LIVEKIT_API_SECRET", ""),
            sarvam_api_key=_text("SARVAM_API_KEY", ""),
            mongodb_uri=_text("MONGODB_URI", ""),
            mongodb_database=_text(
                "MONGODB_DATABASE", "clinic_voice_ai"
            ),
            clinic_timezone=_timezone("CLINIC_TIMEZONE", "Asia/Kolkata"),
            stt_language=_text("STT_LANGUAGE", "hi-IN"),
            stt_stream_type=_text("STT_STREAM_TYPE", "balanced"),
            stt_mode=_text("STT_MODE", "codemix"),
            stt_endpointing=_text("STT_ENDPOINTING", "vad"),
            stt_transcription_timeout=_float(
                "STT_TRANSCRIPTION_TIMEOUT", 6.0
            ),
            llm_model=_text("LLM_MODEL", "sarvam-105b"),
            llm_timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 12.0),
            llm_max_tokens=_int("LLM_MAX_TOKENS", 200),
            tts_language=_text("TTS_LANGUAGE", "hi-IN"),
            tts_model=_text("TTS_MODEL", "bulbul:v3"),
            tts_speaker=_text("TTS_SPEAKER", "shubh"),
            tts_pace=_float("TTS_PACE", 1.0),
            tts_sample_rate=_int("TTS_SAMPLE_RATE", 24000),
            tts_timeout_seconds=_float("TTS_TIMEOUT_SECONDS", 8.0),
            tts_min_buffer_size=_int("TTS_MIN_BUFFER_SIZE", 50),
            tts_max_chunk_length=_int("TTS_MAX_CHUNK_LENGTH", 150),
            vad_min_speech_duration=_float(
                "VAD_MIN_SPEECH_DURATION", 0.10
            ),
            vad_min_silence_duration=_float(
                "VAD_MIN_SILENCE_DURATION", 0.40
            ),
            vad_prefix_padding_duration=_float(
                "VAD_PREFIX_PADDING_DURATION", 0.30
            ),
            vad_activation_threshold=_float(
                "VAD_ACTIVATION_THRESHOLD", 0.50
            ),
            vad_deactivation_threshold=_float(
                "VAD_DEACTIVATION_THRESHOLD", 0.35
            ),
            min_endpointing_delay=_float("MIN_ENDPOINTING_DELAY", 0.50),
            max_endpointing_delay=_float("MAX_ENDPOINTING_DELAY", 2.50),
            interruption_min_duration=_float(
                "INTERRUPTION_MIN_DURATION", 0.5
            ),
            preemptive_tts=_bool("PREEMPTIVE_TTS", False),
            session_max_unrecoverable_errors=_int(
                "SESSION_MAX_UNRECOVERABLE_ERRORS", 10
            ),
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
            openai_api_key=_text("OPENAI_API_KEY", ""),
            rag_enabled=_bool("RAG_ENABLED", True),
            openai_embedding_model=_text(
                "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
            ),
            rag_top_k=_int("RAG_TOP_K", 3),
            rag_min_score=_float("RAG_MIN_SCORE", 0.25),
            rag_chunk_chars=_int("RAG_CHUNK_CHARS", 700),
            rag_chunk_overlap=_int("RAG_CHUNK_OVERLAP", 100),
            rag_timeout_seconds=_float("RAG_TIMEOUT_SECONDS", 4.0),
            rag_max_upload_bytes=_int(
                "RAG_MAX_UPLOAD_BYTES", 5_000_000
            ),
            rag_max_pdf_pages=_int("RAG_MAX_PDF_PAGES", 50),
            jwt_secret=_text("JWT_SECRET", ""),
            jwt_algorithm=_text("JWT_ALGORITHM", "HS256").upper(),
            jwt_expire_minutes=_int("JWT_EXPIRE_MINUTES", 480),
            auth_cookie_name=_text(
                "AUTH_COOKIE_NAME", "clinic_access_token"
            ),
            cookie_secure=_bool("COOKIE_SECURE", False),
            cookie_samesite=_text(
                "COOKIE_SAMESITE", "lax"
            ).lower(),
            log_level=_text("LOG_LEVEL", "INFO").upper(),
            sentry_dsn=_text("SENTRY_DSN", ""),
            sentry_environment=_text(
                "SENTRY_ENVIRONMENT", "production"
            ),
            rate_limit_enabled=_bool("RATE_LIMIT_ENABLED", True),
            trust_proxy_headers=_bool("TRUST_PROXY_HEADERS", True),
        )

    def validate(self) -> None:
        """Raise one readable error listing every invalid setting."""
        errors: list[str] = []

        required = {
            "LIVEKIT_URL": self.livekit_url,
            "LIVEKIT_API_KEY": self.livekit_api_key,
            "LIVEKIT_API_SECRET": self.livekit_api_secret,
            "SARVAM_API_KEY": self.sarvam_api_key,
            "MONGODB_URI": self.mongodb_uri,
            "JWT_SECRET": self.jwt_secret,
        }
        for name, value in required.items():
            if not value:
                errors.append(f"{name} is required")

        if self.livekit_url and not (
            self.livekit_url.startswith("wss://")
            or self.livekit_url.startswith("ws://localhost")
            or self.livekit_url.startswith("ws://127.0.0.1")
        ):
            errors.append(
                "LIVEKIT_URL must start with wss:// "
                "(or ws://localhost for local development)"
            )

        if self.mongodb_uri and not self.mongodb_uri.startswith(
            ("mongodb://", "mongodb+srv://")
        ):
            errors.append(
                "MONGODB_URI must start with mongodb:// or mongodb+srv://"
            )

        if self.jwt_secret and len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET must be at least 32 characters")

        if self.jwt_algorithm not in JWT_ALGORITHMS:
            errors.append(
                f"JWT_ALGORITHM must be one of {sorted(JWT_ALGORITHMS)}"
            )

        if self.jwt_expire_minutes <= 0:
            errors.append("JWT_EXPIRE_MINUTES must be greater than 0")

        if self.cookie_samesite not in COOKIE_SAMESITE_VALUES:
            errors.append(
                "COOKIE_SAMESITE must be lax, strict, or none"
            )

        if self.log_level not in LOG_LEVELS:
            errors.append(
                f"LOG_LEVEL must be one of {sorted(LOG_LEVELS)}"
            )

        if not 0.3 <= self.tts_pace <= 3.0:
            errors.append("TTS_PACE must be between 0.3 and 3.0")

        if not 30 <= self.tts_min_buffer_size <= 200:
            errors.append("TTS_MIN_BUFFER_SIZE must be between 30 and 200")

        if not 50 <= self.tts_max_chunk_length <= 500:
            errors.append(
                "TTS_MAX_CHUNK_LENGTH must be between 50 and 500"
            )

        if self.tts_sample_rate not in TTS_SAMPLE_RATES:
            errors.append(
                "TTS_SAMPLE_RATE must be one of "
                f"{sorted(TTS_SAMPLE_RATES)}"
            )

        if self.tts_timeout_seconds <= 0:
            errors.append("TTS_TIMEOUT_SECONDS must be greater than 0")

        if self.stt_endpointing != "vad":
            errors.append(
                "STT_ENDPOINTING must be 'vad'; the agent relies on "
                "Sarvam's server-side turn detection"
            )

        if self.stt_transcription_timeout <= 0:
            errors.append(
                "STT_TRANSCRIPTION_TIMEOUT must be greater than 0"
            )

        if self.llm_timeout_seconds <= 0:
            errors.append("LLM_TIMEOUT_SECONDS must be greater than 0")

        if self.llm_max_tokens <= 0:
            errors.append("LLM_MAX_TOKENS must be greater than 0")

        if self.session_max_unrecoverable_errors <= 0:
            errors.append(
                "SESSION_MAX_UNRECOVERABLE_ERRORS must be greater than 0"
            )

        if self.vad_min_speech_duration <= 0:
            errors.append(
                "VAD_MIN_SPEECH_DURATION must be greater than 0"
            )

        if self.vad_min_silence_duration < MIN_TURN_DETECTOR_VAD_SILENCE:
            errors.append(
                "VAD_MIN_SILENCE_DURATION must be at least "
                f"{MIN_TURN_DETECTOR_VAD_SILENCE} for the turn detector"
            )

        if self.vad_prefix_padding_duration < 0:
            errors.append(
                "VAD_PREFIX_PADDING_DURATION cannot be negative"
            )

        if not 0 < self.vad_activation_threshold <= 1:
            errors.append(
                "VAD_ACTIVATION_THRESHOLD must be greater than 0 "
                "and at most 1"
            )

        if not 0 < self.vad_deactivation_threshold:
            errors.append(
                "VAD_DEACTIVATION_THRESHOLD must be greater than 0"
            )

        if (
            self.vad_deactivation_threshold
            >= self.vad_activation_threshold
        ):
            errors.append(
                "VAD_DEACTIVATION_THRESHOLD must be less than "
                "VAD_ACTIVATION_THRESHOLD"
            )

        if self.min_endpointing_delay < 0:
            errors.append("MIN_ENDPOINTING_DELAY cannot be negative")

        if self.max_endpointing_delay < self.min_endpointing_delay:
            errors.append(
                "MAX_ENDPOINTING_DELAY must be >= MIN_ENDPOINTING_DELAY"
            )

        if self.interruption_min_duration < 0:
            errors.append(
                "INTERRUPTION_MIN_DURATION cannot be negative"
            )

        if self.analysis_max_attempts < 1:
            errors.append("ANALYSIS_MAX_ATTEMPTS must be at least 1")

        if self.analysis_poll_seconds <= 0:
            errors.append("ANALYSIS_POLL_SECONDS must be greater than 0")

        if self.analysis_timeout_seconds <= 0:
            errors.append(
                "ANALYSIS_TIMEOUT_SECONDS must be greater than 0"
            )

        if self.analysis_transcript_chars < 100:
            errors.append(
                "ANALYSIS_TRANSCRIPT_CHARS must be at least 100"
            )

        if self.rag_top_k <= 0:
            errors.append("RAG_TOP_K must be greater than 0")

        if not 0 <= self.rag_min_score <= 1:
            errors.append("RAG_MIN_SCORE must be between 0 and 1")

        if self.rag_chunk_chars < 100:
            errors.append("RAG_CHUNK_CHARS must be at least 100")

        if self.rag_chunk_overlap < 0:
            errors.append("RAG_CHUNK_OVERLAP cannot be negative")

        if self.rag_chunk_overlap >= self.rag_chunk_chars:
            errors.append(
                "RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_CHARS"
            )

        if self.rag_timeout_seconds <= 0:
            errors.append("RAG_TIMEOUT_SECONDS must be greater than 0")

        if self.rag_max_upload_bytes < 1024:
            errors.append(
                "RAG_MAX_UPLOAD_BYTES must be at least 1024"
            )

        if self.rag_max_pdf_pages <= 0:
            errors.append("RAG_MAX_PDF_PAGES must be greater than 0")

        if errors:
            raise RuntimeError(
                "Invalid configuration:\n- " + "\n- ".join(errors)
            )

    @property
    def sarvam_llm_base_url(self) -> str:
        if self.analysis_model in SARVAM_V1_MODELS:
            return "https://api.sarvam.ai/v1"
        return _text("SARVAM_LLM_BASE_URL", DEFAULT_SARVAM_BASE_URL)


settings = Settings.from_env()
