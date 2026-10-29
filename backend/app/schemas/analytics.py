from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsRange(BaseModel):
    from_date: str
    to_date: str
    run_id: str | None = None


class CallMetrics(BaseModel):
    total: int = 0
    completed: int = 0
    average_duration_seconds: float | None = None
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_sentiment: dict[str, int] = Field(default_factory=dict)


class AppointmentMetrics(BaseModel):
    total: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)


class AnalyticsSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    range: AnalyticsRange
    calls: CallMetrics
    appointments: AppointmentMetrics
    booking_conversion_rate: float = 0.0
    latency: dict[str, Any] = Field(default_factory=dict)
    generated_at: str
