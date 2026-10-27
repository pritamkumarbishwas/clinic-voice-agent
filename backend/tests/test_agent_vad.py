from types import SimpleNamespace

import agent


def test_is_stt_error_only_matches_stt_errors():
    assert agent._is_stt_error(SimpleNamespace(type="stt_error"))
    assert not agent._is_stt_error(SimpleNamespace(type="llm_error"))
    assert not agent._is_stt_error(None)


def test_prewarm_loads_configured_silero_options(monkeypatch):
    captured = {}

    class FakeVAD:
        @classmethod
        def load(cls, **kwargs):
            captured.update(kwargs)
            return "vad-instance"

    monkeypatch.setattr(agent.silero, "VAD", FakeVAD)
    monkeypatch.setattr(
        agent,
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
