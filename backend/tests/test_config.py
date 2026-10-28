import pytest

from app.config import Settings, sanitize_run_id

VAD_ENV_KEYS = (
    "VAD_MIN_SPEECH_DURATION",
    "VAD_MIN_SILENCE_DURATION",
    "VAD_PREFIX_PADDING_DURATION",
    "VAD_ACTIVATION_THRESHOLD",
    "VAD_DEACTIVATION_THRESHOLD",
    "MIN_ENDPOINTING_DELAY",
    "MAX_ENDPOINTING_DELAY",
    "STT_TRANSCRIPTION_TIMEOUT",
)


def _clear_vad_env(monkeypatch):
    for key in VAD_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _set_required_env(monkeypatch):
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test-secret")
    monkeypatch.setenv("SARVAM_API_KEY", "test-sarvam-key")


def test_vad_defaults_are_tuned_for_natural_speech(monkeypatch):
    _clear_vad_env(monkeypatch)

    config = Settings.from_env()

    assert config.vad_min_speech_duration == 0.10
    assert config.vad_min_silence_duration == 0.40
    assert config.vad_prefix_padding_duration == 0.30
    assert config.vad_activation_threshold == 0.50
    assert config.vad_deactivation_threshold == 0.35
    assert config.min_endpointing_delay == 0.50
    assert config.max_endpointing_delay == 2.50
    assert config.stt_transcription_timeout == 6.0


def test_stt_transcription_timeout_must_be_positive(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("STT_TRANSCRIPTION_TIMEOUT", "0")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env().validate()

    assert "STT_TRANSCRIPTION_TIMEOUT must be greater than 0" in str(
        error.value
    )


def test_llm_timeout_default(monkeypatch):
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)

    assert Settings.from_env().llm_timeout_seconds == 12.0


def test_llm_timeout_must_be_positive(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env().validate()

    assert "LLM_TIMEOUT_SECONDS must be greater than 0" in str(error.value)


def test_llm_max_tokens_default(monkeypatch):
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)

    assert Settings.from_env().llm_max_tokens == 200


def test_llm_max_tokens_must_be_positive(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("LLM_MAX_TOKENS", "0")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env().validate()

    assert "LLM_MAX_TOKENS must be greater than 0" in str(error.value)


def test_tts_defaults_are_clear_and_streaming(monkeypatch):
    for key in (
        "TTS_SAMPLE_RATE",
        "TTS_TIMEOUT_SECONDS",
        "TTS_PACE",
        "TTS_MIN_BUFFER_SIZE",
        "TTS_MAX_CHUNK_LENGTH",
    ):
        monkeypatch.delenv(key, raising=False)

    config = Settings.from_env()

    assert config.tts_sample_rate == 24000
    assert config.tts_timeout_seconds == 8.0
    assert config.tts_pace == 1.0
    assert config.tts_min_buffer_size == 50
    assert config.tts_max_chunk_length == 150


def test_tts_validation_matches_sarvam_limits(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("TTS_PACE", "0.2")
    monkeypatch.setenv("TTS_MIN_BUFFER_SIZE", "20")
    monkeypatch.setenv("TTS_MAX_CHUNK_LENGTH", "40")
    monkeypatch.setenv("TTS_SAMPLE_RATE", "12345")
    monkeypatch.setenv("TTS_TIMEOUT_SECONDS", "0")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env().validate()

    message = str(error.value)
    assert "TTS_PACE must be between 0.3 and 3.0" in message
    assert "TTS_MIN_BUFFER_SIZE must be between 30 and 200" in message
    assert "TTS_MAX_CHUNK_LENGTH must be between 50 and 500" in message
    assert "TTS_SAMPLE_RATE must be one of" in message
    assert "TTS_TIMEOUT_SECONDS must be greater than 0" in message


def test_session_error_threshold_default_and_validation(monkeypatch):
    monkeypatch.delenv("SESSION_MAX_UNRECOVERABLE_ERRORS", raising=False)
    assert Settings.from_env().session_max_unrecoverable_errors == 10

    _set_required_env(monkeypatch)
    monkeypatch.setenv("SESSION_MAX_UNRECOVERABLE_ERRORS", "0")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env().validate()

    assert "SESSION_MAX_UNRECOVERABLE_ERRORS must be greater than 0" in str(
        error.value
    )


def test_vad_silence_below_turn_detector_minimum_is_rejected(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("VAD_MIN_SILENCE_DURATION", "0.2")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env().validate()

    assert "VAD_MIN_SILENCE_DURATION must be at least 0.25" in str(
        error.value
    )


def test_manual_stt_endpointing_is_rejected(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("STT_ENDPOINTING", "manual")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env().validate()

    assert "STT_ENDPOINTING must be 'vad'" in str(error.value)


def test_vad_validation_rejects_invalid_values(monkeypatch):
    _clear_vad_env(monkeypatch)
    _set_required_env(monkeypatch)
    monkeypatch.setenv("VAD_MIN_SPEECH_DURATION", "0")
    monkeypatch.setenv("VAD_MIN_SILENCE_DURATION", "-0.1")
    monkeypatch.setenv("VAD_PREFIX_PADDING_DURATION", "-0.1")
    monkeypatch.setenv("VAD_ACTIVATION_THRESHOLD", "0")
    monkeypatch.setenv("VAD_DEACTIVATION_THRESHOLD", "0.7")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env().validate()

    message = str(error.value)
    assert "VAD_MIN_SPEECH_DURATION" in message
    assert "VAD_MIN_SILENCE_DURATION" in message
    assert "VAD_PREFIX_PADDING_DURATION" in message
    assert "VAD_ACTIVATION_THRESHOLD" in message
    assert "VAD_DEACTIVATION_THRESHOLD" in message


def test_sanitize_run_id_accepts_safe_values():
    assert sanitize_run_id("baseline-1") == "baseline-1"
    assert sanitize_run_id(" baseline 1 ") == "baseline 1"
    assert sanitize_run_id("run_2026-10") == "run_2026-10"


def test_sanitize_run_id_rejects_unsafe_values():
    assert sanitize_run_id("") is None
    assert sanitize_run_id("   ") is None
    assert sanitize_run_id("bad/slash") is None
    assert sanitize_run_id("x" * 49) is None
    assert sanitize_run_id(None) is None


def test_production_requires_secure_cookie_explicit_hosts_and_cors(
    monkeypatch,
):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("TRUSTED_HOSTS", "*")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env().validate()

    message = str(error.value)
    assert "COOKIE_SECURE must be true in production" in message
    assert "TRUSTED_HOSTS must list explicit hosts in production" in message
    assert "CORS_ORIGINS cannot contain localhost in production" in message


def test_worker_and_proxy_flags_default_to_safe_values(monkeypatch):
    monkeypatch.delenv("ANALYSIS_WORKER_ENABLED", raising=False)
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)

    config = Settings.from_env()

    assert config.analysis_worker_enabled is False
    assert config.trust_proxy_headers is False


def test_rag_max_documents_must_be_positive(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("RAG_MAX_DOCUMENTS", "0")

    with pytest.raises(RuntimeError) as error:
        Settings.from_env().validate()

    assert "RAG_MAX_DOCUMENTS must be at least 1" in str(error.value)
