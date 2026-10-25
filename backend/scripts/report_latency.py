
import asyncio
import math
import json

from app.database import call_turns, client


METRICS = {
    "endpoint_latency_ms": "Speech end → endpoint decision",
    "stt_latency_ms": "Speech end → final transcript",
    "llm_latency_ms": "LLM request → first token",
    "tts_latency_ms": "TTS request → first audio",
    "end_to_audio_ms": "Speech end → response audio",
}


def percentile(values, p):
    values = sorted(values)
    if not values:
        return None

    # Nearest-rank percentile.
    rank = max(1, math.ceil((p / 100) * len(values)))
    return round(values[rank - 1], 2)


async def main():
    try:
        cursor = call_turns.find({})
        rows = await cursor.to_list(length=100000)

        report = {}

        for field, label in METRICS.items():
            values = [
                float(row[field])
                for row in rows
                if isinstance(row.get(field), (int, float))
                and row[field] >= 0
            ]

            report[field] = {
                "label": label,
                "sample_count": len(values),
                "p50_ms": percentile(values, 50),
                "p95_ms": percentile(values, 95),
            }

        print(json.dumps(report, indent=2))

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
