from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings
from app.services.voice_session_service import decode_session_token


def rate_limit_key(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=rate_limit_key,
    enabled=settings.rate_limit_enabled,
)


async def optional_voice_session(request: Request) -> dict | None:
    token = request.headers.get("x-voice-session")
    if not token:
        return None
    return decode_session_token(token)
