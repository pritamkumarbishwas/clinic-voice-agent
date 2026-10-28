from app.config import settings

AGENT_NAME = settings.livekit_agent_name
TRANSCRIPT_TOPIC = "transcripts"
CONTROL_TOPIC = "control"
STT_REPEAT_PROMPT = (
    "Sorry, main aapki awaaz theek se nahi sun paya. "
    "Kya aap dobara bata sakte hain?"
)
LLM_MAX_RETRIES = 0
TTS_MAX_RETRIES = 0
LLM_FALLBACK_PROMPT = (
    "Sorry, main clinic ki AI receptionist hoon aur abhi system mein "
    "thodi problem aa rahi hai. Kripya thodi der baad dobara call karein."
)
