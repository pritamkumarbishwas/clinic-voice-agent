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
