"""HTTP request and response schemas."""

from app.schemas.analytics import AnalyticsSummary
from app.schemas.appointments import (
    AppointmentCreate,
    AppointmentListItem,
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentUpdate,
    AvailabilityResponse,
    SlotResponse,
)
from app.schemas.calls import (
    CallDetailResponse,
    CallListItem,
    CallListResponse,
    TranscriptEntry,
    TranscriptResponse,
)
from app.schemas.common import (
    ErrorDetail,
    ErrorResponse,
    MessageResponse,
    Page,
    PageMeta,
)
from app.schemas.doctors import DoctorListResponse, DoctorPublic
from app.schemas.health import LivenessResponse, ReadinessResponse
from app.schemas.voice import VoiceSessionRequest, VoiceSessionResponse

__all__ = [
    "AnalyticsSummary",
    "AppointmentCreate",
    "AppointmentListItem",
    "AppointmentListResponse",
    "AppointmentResponse",
    "AppointmentUpdate",
    "AvailabilityResponse",
    "CallDetailResponse",
    "CallListItem",
    "CallListResponse",
    "DoctorListResponse",
    "DoctorPublic",
    "ErrorDetail",
    "ErrorResponse",
    "LivenessResponse",
    "MessageResponse",
    "Page",
    "PageMeta",
    "ReadinessResponse",
    "SlotResponse",
    "TranscriptEntry",
    "TranscriptResponse",
    "VoiceSessionRequest",
    "VoiceSessionResponse",
]
