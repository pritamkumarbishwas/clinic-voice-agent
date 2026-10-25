from app.services.analytics_worker import (
    _parse_analysis_json,
    analyze_transcript,
)


def test_empty_transcript_falls_back_cleanly():
    result = analyze_transcript([])

    assert result["sentiment"] == "unknown"
    assert result["caller_turns"] == 0
    assert result["analyzer"] == "rule-based-v3"


def test_positive_transcript():
    transcript = [
        {"role": "user", "text": "Thank you, bahut accha service"},
        {"role": "assistant", "text": "Dhanyavaad."},
    ]

    result = analyze_transcript(transcript)

    assert result["sentiment"] == "positive"
    assert result["caller_turns"] == 1
    assert result["assistant_turns"] == 1


def test_negative_transcript():
    transcript = [
        {"role": "user", "text": "Mujhe problem hai, service bahut bad"},
    ]

    assert analyze_transcript(transcript)["sentiment"] == "negative"


def test_parse_valid_json():
    parsed = _parse_analysis_json(
        '{"summary": "Caller booked a slot.", '
        '"sentiment": "positive", "intent": "book_appointment", '
        '"follow_up": "", "compliance_flags": []}'
    )

    assert parsed is not None
    assert parsed.intent == "book_appointment"


def test_parse_fenced_json():
    parsed = _parse_analysis_json(
        "```json\n"
        '{"summary": "Caller asked about timings.", '
        '"sentiment": "neutral", "intent": "check_availability", '
        '"follow_up": "Call back", "compliance_flags": []}\n'
        "```"
    )

    assert parsed is not None
    assert parsed.follow_up == "Call back"


def test_parse_invalid_json_returns_none():
    assert _parse_analysis_json("not json") is None
    assert _parse_analysis_json('{"summary": ""}') is None
