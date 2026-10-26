import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
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

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class TranscriptAnalysis(BaseModel):
    summary: str = Field(min_length=1, max_length=1200)
    sentiment: Literal["positive", "neutral", "negative", "unknown"] = "unknown"
    intent: str = Field(default="unknown", max_length=120)
    follow_up: str = Field(default="", max_length=500)
    compliance_flags: list[str] = Field(default_factory=list)


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
    """Cheap, deterministic analysis used when the LLM is unavailable."""
    user_messages = _messages_by_role(transcript, "user")
    assistant_messages = _messages_by_role(transcript, "assistant")

    if not user_messages:
        return {
            "summary": "No caller transcript was recorded.",
            "sentiment": "unknown",
            "intent": "unknown",
            "follow_up": "",
            "compliance_flags": [],
            "caller_turns": 0,
            "assistant_turns": len(assistant_messages),
            "analyzer": "rule-based-v3",
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
        "intent": "unknown",
        "follow_up": "",
        "compliance_flags": [],
        "caller_turns": len(user_messages),
        "assistant_turns": len(assistant_messages),
        "analyzer": "rule-based-v3",
    }


def _build_transcript_text(transcript: list, limit: int) -> str:
    lines = []
    for item in transcript:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = item.get("text")
        if role not in {"user", "assistant"} or not isinstance(text, str):
            continue
        text = " ".join(text.split())
        if not text:
            continue
        speaker = "Caller" if role == "user" else "AI receptionist"
        lines.append(f"{speaker}: {text}")

    joined = "\n".join(lines)
    if len(joined) > limit:
        joined = joined[-limit:]
    return joined


def _parse_analysis_json(raw: str) -> TranscriptAnalysis | None:
    cleaned = _JSON_FENCE.sub("", (raw or "").strip()).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None

    try:
        return TranscriptAnalysis.model_validate(payload)
    except ValidationError:
        return None


async def analyze_with_llm(
    transcript: list,
    booking_outcome: str,
) -> TranscriptAnalysis | None:
    api_key = settings.sarvam_api_key
    if not api_key:
        logger.info("SARVAM_API_KEY is missing; using rule-based analysis")
        return None

    transcript_text = _build_transcript_text(
        transcript, settings.analysis_transcript_chars
    )
    if not transcript_text:
        return None

    system_prompt = (
        "You analyse finished phone calls for an Indian clinic receptionist. "
        "Return ONLY valid JSON with keys: summary, sentiment, intent, "
        "follow_up, compliance_flags. "
        "summary must be 2-3 short sentences in English and mention what the "
        "caller wanted and what happened. "
        "sentiment must be one of positive, neutral, negative, unknown. "
        "intent must be short, for example book_appointment, "
        "check_availability, general_question, other. "
        "follow_up must be a short next action or an empty string. "
        "compliance_flags must be a JSON array of short strings; use an empty "
        "array when nothing is wrong. "
        "Do not invent names, phone numbers, doctors, dates or times that are "
        "not in the transcript. Never change the booking outcome provided to "
        "you; it comes from the database and is authoritative."
    )
    user_prompt = (
        f"Booking outcome from the database: {booking_outcome}\n\n"
        f"Transcript:\n{transcript_text}"
    )

    try:
        async with AsyncOpenAI(
            api_key=api_key,
            base_url=settings.sarvam_llm_base_url,
            default_headers={"api-subscription-key": api_key},
        ) as client:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.analysis_model,
                    temperature=0.2,
                    max_tokens=1500,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                ),
                timeout=settings.analysis_timeout_seconds,
            )
    except Exception:
        logger.exception("LLM analysis call failed")
        return None

    content = ""
    if response.choices:
        content = response.choices[0].message.content or ""

    analysis = _parse_analysis_json(content)
    if analysis is None:
        logger.warning("Could not parse LLM analysis JSON: %r", content[:300])
    return analysis


async def process_call(call_id: str) -> dict | None:
    """Idempotently summarise a finished call.

    The booking outcome always comes from the database, never from the LLM.
    """
    call = await calls.find_one(
        {"call_id": call_id},
        {
            "transcript": 1,
            "booking_outcome": 1,
            "analysis_status": 1,
        },
    )
    if call is None:
        return None

    if call.get("analysis_status") == "completed":
        return None

    transcript = call.get("transcript") or []
    outcome = call.get("booking_outcome") or "unknown"
    fallback = analyze_transcript(transcript)
    llm_analysis = await analyze_with_llm(transcript, outcome)

    if llm_analysis is not None and llm_analysis.summary.strip():
        analysis = {
            "summary": llm_analysis.summary.strip(),
            "sentiment": llm_analysis.sentiment,
            "intent": llm_analysis.intent.strip() or "unknown",
            "follow_up": llm_analysis.follow_up.strip(),
            "compliance_flags": llm_analysis.compliance_flags[:10],
            "caller_turns": fallback["caller_turns"],
            "assistant_turns": fallback["assistant_turns"],
            "analyzer": f"llm:{settings.analysis_model}",
        }
    else:
        analysis = fallback

    await calls.update_one(
        {"call_id": call_id},
        {
            "$set": {
                "summary": analysis["summary"],
                "sentiment": analysis["sentiment"],
                "intent": analysis["intent"],
                "follow_up": analysis["follow_up"],
                "compliance_flags": analysis["compliance_flags"],
                "caller_turns": analysis["caller_turns"],
                "assistant_turns": analysis["assistant_turns"],
                "analysis_version": analysis["analyzer"],
                "analysis_status": "completed",
                "analysis_error": None,
                "analysis_locked_at": None,
                "analyzed_at": datetime.now(timezone.utc),
                "booking_outcome": outcome,
            }
        },
    )

    logger.info("Analysed call %s (outcome=%s)", call_id, outcome)
    return analysis
