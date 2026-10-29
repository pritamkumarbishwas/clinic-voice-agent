from pydantic import BaseModel, ConfigDict, Field, field_validator


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=3, max_length=40)
    slot_id: str = Field(min_length=1, max_length=64)

    @field_validator("name", "phone", "slot_id")
    @classmethod
    def clean_text(cls, value: str) -> str:
        cleaned = " ".join((value or "").split())
        if not cleaned:
            raise ValueError("Value cannot be empty")
        return cleaned


class AppointmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str = Field(min_length=1, max_length=64)

    @field_validator("slot_id")
    @classmethod
    def clean_slot_id(cls, value: str) -> str:
        cleaned = " ".join((value or "").split())
        if not cleaned:
            raise ValueError("Value cannot be empty")
        return cleaned


class SlotResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    slot_id: str
    doctor: str
    specialty: str = ""
    start_at: str
    start_at_utc: str
    end_at: str
    local_time: str


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    ok: bool
    doctor: str | None = None
    date: str | None = None
    slots: list[SlotResponse] = Field(default_factory=list)
    message: str = ""


class AppointmentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    ok: bool = True
    appointment_id: str | None = None
    reference: str | None = None
    doctor: str | None = None
    name: str | None = None
    date: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    local_time: str | None = None
    status: str | None = None
    message: str = ""
    idempotency_key: str | None = None
    idempotent_replay: bool = False


class AppointmentListItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    appointment_id: str
    reference: str = ""
    name: str = ""
    phone: str = ""
    doctor_name: str = ""
    start_at: str | None = None
    end_at: str | None = None
    status: str = ""
    call_id: str = ""
    created_at: str | None = None


class AppointmentListResponse(BaseModel):
    items: list[AppointmentListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
