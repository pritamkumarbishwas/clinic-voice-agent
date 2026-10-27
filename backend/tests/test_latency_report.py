from app.services.latency_report import (
    build_markdown,
    build_report,
    percentile,
)


def test_percentile_handles_empty_and_values():
    assert percentile([], 50) is None
    assert percentile([100.0], 95) == 100.0
    assert percentile([100.0, 200.0, 300.0, 400.0], 50) == 200.0
    assert percentile([100.0, 200.0, 300.0, 400.0], 95) == 400.0


def test_build_report_groups_stages_and_calls():
    turns = [
        {
            "call_id": "call-1",
            "run_id": "baseline-1",
            "end_to_audio_ms": 1200,
            "llm_latency_ms": 500,
            "tts_latency_ms": 300,
        },
        {
            "call_id": "call-1",
            "run_id": "baseline-1",
            "end_to_audio_ms": 1400,
            "llm_latency_ms": 600,
            "tts_latency_ms": 350,
        },
        {
            "call_id": "call-2",
            "run_id": "baseline-1",
            "end_to_audio_ms": 900,
            "llm_latency_ms": 400,
            "tts_latency_ms": 250,
        },
    ]
    calls = [
        {
            "call_id": "call-1",
            "booking_outcome": "booked",
            "barge_in_count": 1,
        },
        {
            "call_id": "call-2",
            "booking_outcome": "not_booked",
            "barge_in_count": 0,
        },
    ]

    report = build_report(turns, calls)

    assert report["calls_measured"] == 2
    assert report["turns_measured"] == 3
    assert report["booking_successes"] == 1
    assert report["booking_success_rate"] == 0.5
    assert report["barge_in_count"] == 1
    assert report["metrics"]["end_to_audio_ms"]["p50_ms"] == 1200
    assert len(report["per_call"]) == 2
    assert report["per_call"][0]["call_id"] == "call-1"


def test_build_report_includes_stt_failures_and_empty_calls():
    calls = [
        {
            "call_id": "call-1",
            "booking_outcome": "booked",
            "stt_error_count": 1,
            "stt_timeout_count": 2,
            "empty_transcript_count": 1,
        },
        {
            "call_id": "call-2",
            "booking_outcome": "not_booked",
            "stt_error_count": 0,
            "stt_timeout_count": 0,
            "empty_transcript_count": 0,
        },
        {"call_id": "call-3", "booking_outcome": "not_booked"},
    ]

    report = build_report([], calls)

    assert report["stt_error_count"] == 1
    assert report["stt_timeout_count"] == 2
    assert report["empty_transcript_count"] == 1
    assert report["stt_failure_count"] == 4
    assert report["calls_with_stt_failures"] == 1
    assert report["stt_failure_rate"] == 0.3333
    assert len(report["per_call"]) == 3

    per_call = {row["call_id"]: row for row in report["per_call"]}
    assert per_call["call-1"]["stt_error_count"] == 1
    assert per_call["call-1"]["stt_timeout_count"] == 2
    assert per_call["call-2"]["stt_error_count"] == 0


def test_build_markdown_contains_stage_table():
    report = build_report(
        [
            {
                "call_id": "call-1",
                "end_to_audio_ms": 1000,
                "llm_latency_ms": 400,
                "tts_latency_ms": 200,
            }
        ],
        [{"call_id": "call-1", "booking_outcome": "booked"}],
    )

    markdown = build_markdown(report, "Baseline")

    assert "# Baseline" in markdown
    assert "Speech end -> response audio" in markdown
    assert "STT errors" in markdown
    assert "call-1" in markdown
