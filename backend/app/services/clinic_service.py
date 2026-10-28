import re
from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.database import clinic

_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_PHONE_PATTERN = re.compile(r"^[+0-9()\-\s]{3,40}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_WEBSITE_PATTERN = re.compile(r"^https?://[^\s]+$")
CLINIC_DOCUMENT_ID = "main"
PLACEHOLDER_CLINIC_NAME = "Clinic"


class ClinicHours(BaseModel):
    model_config = ConfigDict(extra="ignore")

    open: str = "10:00"
    close: str = "17:00"
    days: str = Field(default="Mon-Sat", max_length=120)

    @field_validator("open", "close")
    @classmethod
    def validate_time(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not _TIME_PATTERN.fullmatch(cleaned):
            raise ValueError("Time must use HH:MM in 24-hour format")
        return cleaned


class ClinicService(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=300)
    fee: str = Field(default="", max_length=120)

    @field_validator("name", "description", "fee")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join((value or "").split())


class ClinicHoliday(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: str = Field(min_length=10, max_length=10)
    name: str = Field(min_length=1, max_length=120)
    closed: bool = True

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        cleaned = (value or "").strip()
        try:
            datetime.strptime(cleaned, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Holiday date must use YYYY-MM-DD") from exc
        return cleaned

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join((value or "").split())


class ClinicProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="Clinic", min_length=1, max_length=200)
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=254)
    website: str = Field(default="", max_length=300)
    hours: ClinicHours = Field(default_factory=ClinicHours)
    consultation_fee: str = Field(default="", max_length=120)
    services: list[ClinicService] = Field(default_factory=list, max_length=50)
    appointment_policy: str = Field(default="", max_length=1000)
    cancellation_policy: str = Field(default="", max_length=1000)
    holidays: list[ClinicHoliday] = Field(default_factory=list, max_length=100)
    emergency_note: str = Field(default="", max_length=300)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if cleaned and not _PHONE_PATTERN.fullmatch(cleaned):
            raise ValueError("Phone contains unsupported characters")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = (value or "").strip().lower()
        if cleaned and not _EMAIL_PATTERN.fullmatch(cleaned):
            raise ValueError("Email address is invalid")
        return cleaned

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if cleaned and not _WEBSITE_PATTERN.fullmatch(cleaned):
            raise ValueError("Website must start with http:// or https://")
        return cleaned

    @field_validator("services")
    @classmethod
    def clean_services(cls, value: list[ClinicService]) -> list[ClinicService]:
        cleaned = [
            service
            for service in value
            if service.name.strip()
        ]
        return cleaned

    @field_validator("holidays")
    @classmethod
    def clean_holidays(cls, value: list[ClinicHoliday]) -> list[ClinicHoliday]:
        seen: set[str] = set()
        cleaned: list[ClinicHoliday] = []
        for holiday in sorted(value, key=lambda item: item.date):
            if holiday.date in seen:
                continue
            seen.add(holiday.date)
            cleaned.append(holiday)
        return cleaned


DEFAULT_CLINIC = ClinicProfile(
    name=PLACEHOLDER_CLINIC_NAME,
    address="",
    phone="",
    email="",
    website="",
    hours=ClinicHours(),
    consultation_fee="",
    services=[],
    appointment_policy="",
    cancellation_policy="",
    holidays=[],
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


def _as_profile(profile: dict | ClinicProfile) -> ClinicProfile:
    if isinstance(profile, ClinicProfile):
        return profile
    return ClinicProfile.model_validate(profile)


def _is_unconfigured(profile: ClinicProfile) -> bool:
    return profile.name.strip().casefold() == PLACEHOLDER_CLINIC_NAME.casefold()


def closed_holiday_for_date(
    profile: dict | ClinicProfile,
    requested_date: date,
) -> ClinicHoliday | None:
    value = _as_profile(profile)
    target = requested_date.isoformat()
    for holiday in value.holidays:
        if holiday.date == target and holiday.closed:
            return holiday
    return None


def _format_services(profile: ClinicProfile, present) -> list[str]:
    if not profile.services:
        return ["Services offered: Not configured"]
    lines = ["Services offered:"]
    for service in profile.services:
        detail = service.name
        if service.fee:
            detail += f" - fee: {service.fee}"
        if service.description:
            detail += f" - {service.description}"
        lines.append(f"- {detail}")
    return lines


def _format_holidays(
    profile: ClinicProfile,
    present,
    today: date | None,
) -> list[str]:
    holidays = profile.holidays
    if today is not None:
        holidays = [
            holiday
            for holiday in holidays
            if holiday.date >= today.isoformat()
        ]
    if not holidays:
        return ["Upcoming holidays: None configured"]
    lines = ["Upcoming holidays:"]
    for holiday in holidays:
        status = "closed" if holiday.closed else "open with special hours"
        lines.append(f"- {holiday.date}: {holiday.name} ({status})")
    return lines


def format_clinic_for_prompt(
    profile: dict | ClinicProfile,
    today: date | str | None = None,
) -> str:
    value = _as_profile(profile)
    unconfigured = _is_unconfigured(value)

    def present(text: str) -> str:
        cleaned = (text or "").strip()
        return cleaned if cleaned and not unconfigured else "Not configured"

    hours = (
        "Not configured"
        if unconfigured
        else (
            f"{value.hours.open} to {value.hours.close} "
            f"({present(value.hours.days)})"
        )
    )

    parsed_today = None
    if isinstance(today, date):
        parsed_today = today
    elif isinstance(today, str) and today.strip():
        try:
            parsed_today = datetime.strptime(today.strip(), "%Y-%m-%d").date()
        except ValueError:
            parsed_today = None

    lines = [
        f"Clinic name: {present(value.name)}",
        f"Address: {present(value.address)}",
        f"Phone: {present(value.phone)}",
        f"Email: {present(value.email)}",
        f"Website: {present(value.website)}",
        f"Opening hours: {hours}",
        f"Consultation fee: {present(value.consultation_fee)}",
    ]
    if unconfigured:
        lines.extend(
            [
                "Services offered: Not configured",
                "Appointment policy: Not configured",
                "Cancellation policy: Not configured",
                "Upcoming holidays: Not configured",
            ]
        )
    else:
        lines.extend(_format_services(value, present))
        lines.append(
            f"Appointment policy: {present(value.appointment_policy)}"
        )
        lines.append(
            f"Cancellation policy: {present(value.cancellation_policy)}"
        )
        lines.extend(_format_holidays(value, present, parsed_today))
    if value.emergency_note.strip():
        lines.append(f"Emergency note: {value.emergency_note.strip()}")
    return "\n".join(lines)
