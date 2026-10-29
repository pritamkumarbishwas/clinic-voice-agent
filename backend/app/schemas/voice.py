from pydantic import BaseModel, ConfigDict, Field


class VoiceSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = Field(default=None, max_length=48)


class VoiceSessionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    server_url: str
    token: str
    room_name: str
    identity: str
    run_id: str | None = None
    session_token: str
    expires_in: int
