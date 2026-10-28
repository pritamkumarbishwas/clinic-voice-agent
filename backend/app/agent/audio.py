import contextlib

from livekit.agents import APIConnectOptions, tokenize, tts
from livekit.agents.voice.agent_session import SessionConnectOptions
from livekit.plugins import sarvam

from app.agent.constants import LLM_MAX_RETRIES, TTS_MAX_RETRIES
from app.config import settings


def _build_tts() -> tts.TTS:
    """Stream from Sarvam, falling back to its HTTP API if the stream fails."""
    tts_options = {
        "target_language_code": settings.tts_language,
        "model": settings.tts_model,
        "speaker": settings.tts_speaker,
        "pace": settings.tts_pace,
        "speech_sample_rate": settings.tts_sample_rate,
        "min_buffer_size": settings.tts_min_buffer_size,
        "max_chunk_length": settings.tts_max_chunk_length,
        "api_key": settings.sarvam_api_key,
    }
    streaming = sarvam.TTS(**tts_options)
    http_fallback = tts.StreamAdapter(
        tts=sarvam.TTS(**tts_options),
        sentence_tokenizer=tokenize.basic.SentenceTokenizer(),
    )
    return tts.FallbackAdapter(
        [streaming, http_fallback],
        max_retry_per_tts=TTS_MAX_RETRIES,
        sample_rate=settings.tts_sample_rate,
    )


async def _close_tts(tts_instance: tts.TTS) -> None:
    """Close the fallback adapter and its underlying provider clients."""
    with contextlib.suppress(Exception):
        await tts_instance.aclose()

    for child in getattr(tts_instance, "_tts_instances", ()):
        with contextlib.suppress(Exception):
            await child.aclose()


def _session_connect_options() -> SessionConnectOptions:
    return SessionConnectOptions(
        llm_conn_options=APIConnectOptions(
            max_retry=LLM_MAX_RETRIES,
            retry_interval=0.0,
            timeout=settings.llm_timeout_seconds,
        ),
        tts_conn_options=APIConnectOptions(
            max_retry=TTS_MAX_RETRIES,
            retry_interval=0.0,
            timeout=settings.tts_timeout_seconds,
        ),
        max_unrecoverable_errors=settings.session_max_unrecoverable_errors,
    )
