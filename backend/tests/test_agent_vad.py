import asyncio
from types import SimpleNamespace

from livekit.agents import tts

import agent
from app.agent import audio as audio_module
from app.agent import worker as worker_module


def test_is_stt_error_only_matches_stt_errors():
    assert agent._is_stt_error(SimpleNamespace(type="stt_error"))
    assert not agent._is_stt_error(SimpleNamespace(type="llm_error"))
    assert not agent._is_stt_error(None)


def test_is_llm_error_only_matches_llm_errors():
    assert agent._is_llm_error(SimpleNamespace(type="llm_error"))
    assert not agent._is_llm_error(SimpleNamespace(type="stt_error"))
    assert not agent._is_llm_error(None)


def test_is_tts_error_only_matches_tts_errors():
    assert agent._is_tts_error(SimpleNamespace(type="tts_error"))
    assert not agent._is_tts_error(SimpleNamespace(type="llm_error"))
    assert not agent._is_tts_error(None)


def test_is_interrupt_request_requires_control_topic_and_payload():
    assert agent._is_interrupt_request(
        SimpleNamespace(topic="control", data=b'{"type":"interrupt"}')
    )
    assert not agent._is_interrupt_request(
        SimpleNamespace(topic="transcripts", data=b'{"type":"interrupt"}')
    )
    assert not agent._is_interrupt_request(
        SimpleNamespace(topic="control", data=b'{"type":"other"}')
    )
    assert not agent._is_interrupt_request(
        SimpleNamespace(topic="control", data=b"not json")
    )
    assert not agent._is_interrupt_request(
        SimpleNamespace(topic="control", data=b'["interrupt"]')
    )
    assert not agent._is_interrupt_request(None)


def test_build_tts_streams_with_http_fallback(monkeypatch):
    monkeypatch.setattr(
        audio_module,
        "settings",
        SimpleNamespace(
            sarvam_api_key="test-key",
            tts_language="hi-IN",
            tts_model="bulbul:v3",
            tts_speaker="shubh",
            tts_pace=1.0,
            tts_sample_rate=24000,
            tts_min_buffer_size=50,
            tts_max_chunk_length=150,
        ),
    )

    built = agent._build_tts()

    assert isinstance(built, tts.FallbackAdapter)
    assert built.capabilities.streaming
    assert len(built._tts_instances) == 2
    assert built._tts_instances[0].capabilities.streaming
    assert isinstance(built._tts_instances[1], tts.StreamAdapter)


def test_close_tts_closes_adapter_and_underlying_providers():
    closed = []

    class FakeTTS:
        def __init__(self, name):
            self.name = name

        async def aclose(self):
            closed.append(self.name)

    adapter = FakeTTS("adapter")
    adapter._tts_instances = [FakeTTS("streaming"), FakeTTS("http")]

    asyncio.run(agent._close_tts(adapter))

    assert closed == ["adapter", "streaming", "http"]


def test_is_timeout_error_detects_wrapped_and_direct_timeouts():
    direct = TimeoutError("timed out")
    wrapped = RuntimeError("request failed")
    wrapped.__cause__ = direct

    assert agent._is_timeout_error(direct)
    assert agent._is_timeout_error(wrapped)
    assert agent._is_timeout_error(SimpleNamespace(error=direct))
    assert not agent._is_timeout_error(RuntimeError("bad request"))


def test_config_snapshot_records_prompt_metadata():
    snapshot = agent._config_snapshot()

    assert snapshot["prompt"]["version"] == agent.PROMPT_VERSION
    assert snapshot["prompt"]["languages"] == list(agent.SUPPORTED_LANGUAGES)


def test_session_connect_options_disable_llm_retries():
    options = agent._session_connect_options()

    assert options.llm_conn_options.max_retry == agent.LLM_MAX_RETRIES
    assert options.llm_conn_options.timeout == (
        agent.settings.llm_timeout_seconds
    )
    assert options.tts_conn_options.max_retry == agent.TTS_MAX_RETRIES
    assert options.tts_conn_options.timeout == (
        agent.settings.tts_timeout_seconds
    )
    assert options.max_unrecoverable_errors == (
        agent.settings.session_max_unrecoverable_errors
    )


def test_prewarm_loads_configured_silero_options(monkeypatch):
    captured = {}

    class FakeVAD:
        @classmethod
        def load(cls, **kwargs):
            captured.update(kwargs)
            return "vad-instance"

    monkeypatch.setattr(worker_module.silero, "VAD", FakeVAD)
    monkeypatch.setattr(
        worker_module,
        "settings",
        SimpleNamespace(
            validate=lambda: None,
            vad_min_speech_duration=0.10,
            vad_min_silence_duration=0.40,
            vad_prefix_padding_duration=0.30,
            vad_activation_threshold=0.50,
            vad_deactivation_threshold=0.35,
        ),
    )
    proc = SimpleNamespace(userdata={})

    agent.prewarm(proc)

    assert proc.userdata["vad"] == "vad-instance"
    assert captured == {
        "min_speech_duration": 0.10,
        "min_silence_duration": 0.40,
        "prefix_padding_duration": 0.30,
        "activation_threshold": 0.50,
        "deactivation_threshold": 0.35,
    }
