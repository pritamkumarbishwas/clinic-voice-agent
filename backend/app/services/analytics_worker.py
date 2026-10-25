import logging
from datetime import datetime, timezone

from app.database import calls

logger = logging.getLogger("clinic-analytics")

POSITIVE_WORDS = (
    "thank you",
    "thanks",
    "great",
    "good",
    "perfect",
    "धन्यवाद",
    "अच्छा",
    "बढ़िया",
)

NEGATIVE_WORDS = (
    "angry",
    "upset",
    "bad",
    "problem",
    "complaint",
    "परेशान",
    "समस्या",
    "गलत",
)


def _messages_by_role(transcript: list, role: str) -> list[str]:
    return [
        item["text"].strip()
        for item in transcript
        if isinstance(item, dict)
        and item.get("role") == role
        and isinstance(item.get("text"), str)
        and item["text"].strip()
    ]


def analyze_transcript(transcript: list) -> dict:
    """Cheap, deterministic analysis. Never invents words the caller did not say."""
    user_messages = _messages_by_role(transcript, "user")
    assistant_messages = _messages_by_role(transcript, "assistant")

    if not user_messages:
        return {
            "summary": "No caller transcript was recorded.",
            "sentiment": "unknown",
            "caller_turns": 0,
            "assistant_turns": len(assistant_messages),
            "analyzer": "rule-based-v2",
        }

    text = " ".join(user_messages).lower()
    positive = sum(1 for word in POSITIVE_WORDS if word in text)
    negative = sum(1 for word in NEGATIVE_WORDS if word in text)

    if positive > negative:
        sentiment = "positive"
    elif negative > positive:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return {
        "summary": " ".join(user_messages[:3])[:600],
        "sentiment": sentiment,
        "caller_turns": len(user_messages),
        "assistant_turns": len(assistant_messages),
        "analyzer": "rule-based-v2",
    }


async def process_call(call_id: str) -> dict | None:
    """Idempotently summarise a finished call. Booking outcome comes from the DB, not keywords."""
    call = await calls.find_one(
        {"call_id": call_id},
        {"transcript": 1, "booking_outcome": 1, "analysis_status": 1},
    )
    if call is None:
        return None

    if call.get("analysis_status") == "completed":
        return None

    analysis = analyze_transcript(call.get("transcript") or [])
    outcome = call.get("booking_outcome") or "unknown"

    await calls.update_one(
        {"call_id": call_id},
        {
            "$set": {
                "summary": analysis["summary"],
                "sentiment": analysis["sentiment"],
                "caller_turns": analysis["caller_turns"],
                "assistant_turns": analysis["assistant_turns"],
                "analysis_version": analysis["analyzer"],
                "analysis_status": "completed",
                "analyzed_at": datetime.now(timezone.utc),
                "booking_outcome": outcome,
            }
        },
    )

    logger.info("Analysed call %s (outcome=%s)", call_id, outcome)
    return analysis
