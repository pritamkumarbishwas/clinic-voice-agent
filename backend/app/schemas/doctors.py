from pydantic import BaseModel, ConfigDict, Field


class DoctorPublic(BaseModel):
    model_config = ConfigDict(extra="allow")

    doctor_id: str
    name: str
    specialty: str = ""
    active: bool = True
    bio: str = ""
    languages: list[str] = Field(default_factory=list)
    working_days: list[int] = Field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    slot_minutes: int = 30


class DoctorListResponse(BaseModel):
    items: list[DoctorPublic]
