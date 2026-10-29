from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CallListItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    call_id: str = ""
    run_id: str | None = None
    started_at: Any = None
    ended_at: Any = None
    booking_outcome: str = ""
    sentiment: str = ""
    analysis_status: str = ""
    summary: str = ""
    intent: str = ""


class CallListResponse(BaseModel):
    items: list[CallListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class CallDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    call: dict[str, Any]
    turn_metrics: list[dict[str, Any]] = Field(default_factory=list)
    appointment: dict[str, Any] | None = None


class TranscriptEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str = ""
    text: str = ""
    timestamp: Any = None
    message_id: str | None = None


class TranscriptResponse(BaseModel):
    call_id: str
    items: list[TranscriptEntry]
    page: int
    page_size: int
    total: int
    total_pages: int
