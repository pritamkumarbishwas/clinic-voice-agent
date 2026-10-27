import math

LATENCY_FIELDS = {
    "endpoint_latency_ms": "Speech end -> endpoint decision",
    "stt_latency_ms": "Speech end -> final transcript",
    "llm_latency_ms": "LLM request -> first token",
    "tts_latency_ms": "TTS request -> first audio",
    "end_to_audio_ms": "Speech end -> response audio",
    "playback_latency_ms": "Audio frame -> playback started",
}

STT_FAILURE_FIELDS = (
    "stt_error_count",
    "stt_timeout_count",
    "empty_transcript_count",
)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None

    ordered = sorted(values)
    rank = max(1, math.ceil((p / 100) * len(ordered)))
    return round(ordered[rank - 1], 2)


def _numeric_values(rows: list[dict], field: str) -> list[float]:
    values = []
    for row in rows:
        value = row.get(field)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        ):
            values.append(float(value))
    return values


def _stage_summary(values: list[float], label: str) -> dict:
    return {
        "label": label,
        "count": len(values),
        "p50_ms": percentile(values, 50),
        "p95_ms": percentile(values, 95),
        "p99_ms": percentile(values, 99),
        "min_ms": round(min(values), 2) if values else None,
        "max_ms": round(max(values), 2) if values else None,
    }


def _count(call: dict, field: str) -> int:
    value = call.get(field)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0, int(value))
    return 0


def _call_stt_counts(call: dict) -> dict:
    return {field: _count(call, field) for field in STT_FAILURE_FIELDS}


def _per_call(
    turns: list[dict],
    call_docs: list[dict] | None = None,
) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in turns:
        call_id = row.get("call_id")
        if call_id:
            grouped.setdefault(call_id, []).append(row)

    call_by_id = {
        call.get("call_id"): call
        for call in (call_docs or [])
        if call.get("call_id")
    }
    for call_id in call_by_id:
        grouped.setdefault(call_id, [])

    calls = []
    for call_id, rows in grouped.items():
        stage = {
            field: percentile(_numeric_values(rows, field), 50)
            for field in LATENCY_FIELDS
        }
        call_doc = call_by_id.get(call_id, {})
        calls.append(
            {
                "call_id": call_id,
                "run_id": next(
                    (row.get("run_id") for row in rows if row.get("run_id")),
                    call_doc.get("run_id"),
                ),
                "turns": len(rows),
                **_call_stt_counts(call_doc),
                **stage,
            }
        )

    calls.sort(
        key=lambda row: row.get("end_to_audio_ms") or 0,
        reverse=True,
    )
    return calls


def build_report(
    turns: list[dict],
    calls: list[dict] | None = None,
) -> dict:
    call_docs = calls or []
    metrics = {
        field: _stage_summary(_numeric_values(turns, field), label)
        for field, label in LATENCY_FIELDS.items()
    }

    booking_successes = sum(
        1
        for call in call_docs
        if call.get("booking_outcome") == "booked"
    )
    barge_in_count = sum(
        int(call.get("barge_in_count") or 0) for call in call_docs
    )
    stt_counts = {
        field: sum(_count(call, field) for call in call_docs)
        for field in STT_FAILURE_FIELDS
    }
    calls_with_stt_failures = sum(
        1
        for call in call_docs
        if any(_count(call, field) for field in STT_FAILURE_FIELDS)
    )

    return {
        "metrics": metrics,
        "turns_measured": len(turns),
        "calls_measured": len(
            {row.get("call_id") for row in turns if row.get("call_id")}
        ) if not call_docs else len(call_docs),
        "booking_successes": booking_successes,
        "booking_success_rate": (
            round(booking_successes / len(call_docs), 4)
            if call_docs
            else None
        ),
        "barge_in_count": barge_in_count,
        "stt_error_count": stt_counts["stt_error_count"],
        "stt_timeout_count": stt_counts["stt_timeout_count"],
        "empty_transcript_count": stt_counts["empty_transcript_count"],
        "stt_failure_count": sum(stt_counts.values()),
        "calls_with_stt_failures": calls_with_stt_failures,
        "stt_failure_rate": (
            round(calls_with_stt_failures / len(call_docs), 4)
            if call_docs
            else None
        ),
        "per_call": _per_call(turns, call_docs),
    }


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else str(value)


def build_markdown(report: dict, title: str) -> str:
    rate = report.get("booking_success_rate")
    rate_text = "n/a" if rate is None else f"{round(rate * 100)}%"
    stt_rate = report.get("stt_failure_rate")
    stt_rate_text = (
        "n/a" if stt_rate is None else f"{round(stt_rate * 100)}%"
    )

    lines = [
        f"# {title}",
        "",
        f"- Turns measured: {report['turns_measured']}",
        f"- Calls measured: {report['calls_measured']}",
        f"- Booking success rate: {rate_text}",
        f"- Barge-ins recorded: {report.get('barge_in_count', 0)}",
        f"- STT errors: {report.get('stt_error_count', 0)}",
        f"- STT timeouts: {report.get('stt_timeout_count', 0)}",
        f"- Empty final transcripts: {report.get('empty_transcript_count', 0)}",
        (
            f"- Calls with STT failures: "
            f"{report.get('calls_with_stt_failures', 0)} "
            f"({stt_rate_text})"
        ),
        "",
        "| Stage | Samples | p50 (ms) | p95 (ms) | p99 (ms) | Min | Max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for metric in report["metrics"].values():
        lines.append(
            f"| {metric['label']} | {metric['count']} | "
            f"{_fmt(metric['p50_ms'])} | {_fmt(metric['p95_ms'])} | "
            f"{_fmt(metric['p99_ms'])} | {_fmt(metric['min_ms'])} | "
            f"{_fmt(metric['max_ms'])} |"
        )

    per_call = report.get("per_call") or []
    if per_call:
        lines.extend(
            [
                "",
                "## Calls",
                "",
                (
                    "| Call | Turns | E2E p50 (ms) | LLM p50 (ms) | "
                    "TTS p50 (ms) | STT failures |"
                ),
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for call in per_call[:50]:
            stt_failures = sum(
                call.get(field, 0) for field in STT_FAILURE_FIELDS
            )
            lines.append(
                f"| {call['call_id']} | {call['turns']} | "
                f"{_fmt(call.get('end_to_audio_ms'))} | "
                f"{_fmt(call.get('llm_latency_ms'))} | "
                f"{_fmt(call.get('tts_latency_ms'))} | "
                f"{stt_failures} |"
            )

    return "\n".join(lines) + "\n"
