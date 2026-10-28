from app.agent.constants import LLM_MAX_RETRIES, TTS_MAX_RETRIES
from app.config import settings
from app.prompts.receptionist import PROMPT_VERSION, SUPPORTED_LANGUAGES


def _config_snapshot() -> dict:
    return {
        "stt": {
            "language": settings.stt_language,
            "stream_type": settings.stt_stream_type,
            "mode": settings.stt_mode,
            "endpointing": settings.stt_endpointing,
            "transcription_timeout": settings.stt_transcription_timeout,
        },
        "llm": {
            "model": settings.llm_model,
            "timeout_seconds": settings.llm_timeout_seconds,
            "max_tokens": settings.llm_max_tokens,
            "max_retries": LLM_MAX_RETRIES,
        },
        "tts": {
            "language": settings.tts_language,
            "model": settings.tts_model,
            "speaker": settings.tts_speaker,
            "pace": settings.tts_pace,
            "sample_rate": settings.tts_sample_rate,
            "timeout_seconds": settings.tts_timeout_seconds,
            "max_retries": TTS_MAX_RETRIES,
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
        "prompt": {
            "version": PROMPT_VERSION,
            "languages": list(SUPPORTED_LANGUAGES),
        },
    }
