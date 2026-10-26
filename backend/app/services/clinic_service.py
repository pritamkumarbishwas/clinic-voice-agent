import re
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.database import clinic

_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_PHONE_PATTERN = re.compile(r"^[+0-9()\-\s]{3,40}$")
CLINIC_DOCUMENT_ID = "main"


class ClinicHours(BaseModel):
    model_config = ConfigDict(extra="ignore")

    open: str = "10:00"
    close: str = "17:00"
    days: str = Field(default="Mon-Sat", max_length=80)

    @field_validator("open", "close")
    @classmethod
    def validate_time(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not _TIME_PATTERN.fullmatch(cleaned):
            raise ValueError("Time must use HH:MM in 24-hour format")
        return cleaned


class ClinicProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="Clinic", min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=40)
    hours: ClinicHours = Field(default_factory=ClinicHours)
    consultation_fee: str = Field(default="", max_length=120)
    emergency_note: str = Field(default="", max_length=300)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if cleaned and not _PHONE_PATTERN.fullmatch(cleaned):
            raise ValueError("Phone contains unsupported characters")
        return cleaned


DEFAULT_CLINIC = ClinicProfile(
    name="Clinic",
    address="",
    phone="",
    hours=ClinicHours(),
    consultation_fee="",
    emergency_note="",
)


def _normalize_profile(document: dict) -> dict:
    profile = ClinicProfile.model_validate(document)
    return profile.model_dump()


async def get_clinic_profile() -> dict:
    document = await clinic.find_one({"_id": CLINIC_DOCUMENT_ID})
    if document is None:
        return DEFAULT_CLINIC.model_dump()
    return _normalize_profile(document)


async def update_clinic_profile(profile: ClinicProfile) -> dict:
    payload = profile.model_dump()
    payload["updated_at"] = datetime.now(timezone.utc)

    await clinic.update_one(
        {"_id": CLINIC_DOCUMENT_ID},
        {"$set": payload},
        upsert=True,
    )
    return profile.model_dump()


def format_clinic_for_prompt(profile: dict | ClinicProfile) -> str:
    if isinstance(profile, ClinicProfile):
        value = profile
    else:
        value = ClinicProfile.model_validate(profile)

    def present(text: str) -> str:
        cleaned = (text or "").strip()
        return cleaned if cleaned else "Not configured"

    lines = [
        f"Clinic name: {present(value.name)}",
        f"Address: {present(value.address)}",
        f"Phone: {present(value.phone)}",
        (
            "Opening hours: "
            f"{value.hours.open} to {value.hours.close} "
            f"({present(value.hours.days)})"
        ),
        f"Consultation fee: {present(value.consultation_fee)}",
    ]
    if value.emergency_note.strip():
        lines.append(f"Emergency note: {value.emergency_note.strip()}")
    return "\n".join(lines)
