from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.services.appointment_service import build_query, day_bounds_utc
from app.services.clinic_service import (
    DEFAULT_CLINIC,
    ClinicHoliday,
    ClinicProfile,
    closed_holiday_for_date,
    format_clinic_for_prompt,
)


def test_clinic_prompt_marks_missing_details():
    prompt = format_clinic_for_prompt({"name": "Test Clinic"})

    assert "Clinic name: Test Clinic" in prompt
    assert "Address: Not configured" in prompt
    assert "Opening hours: 10:00 to 17:00 (Mon-Sat)" in prompt


def test_default_clinic_does_not_expose_placeholder_hours():
    prompt = format_clinic_for_prompt(DEFAULT_CLINIC)

    assert "Clinic name: Not configured" in prompt
    assert "Opening hours: Not configured" in prompt
    assert "10:00 to 17:00" not in prompt


def test_clinic_profile_rejects_invalid_time():
    with pytest.raises(ValidationError):
        ClinicProfile.model_validate(
            {"name": "Test Clinic", "hours": {"open": "25:00"}}
        )


def test_clinic_profile_ignores_storage_fields():
    profile = ClinicProfile.model_validate(
        {
            "_id": "main",
            "name": "Test Clinic",
            "hours": {"open": "09:30", "close": "18:00"},
            "updated_at": datetime.now(timezone.utc),
        }
    )

    assert profile.hours.open == "09:30"
    assert profile.hours.close == "18:00"


def test_clinic_profile_formats_services_and_policies():
    prompt = format_clinic_for_prompt(
        {
            "name": "Test Clinic",
            "email": "hello@example.com",
            "website": "https://example.com",
            "services": [
                {
                    "name": "General consultation",
                    "fee": "500 rupees",
                    "description": "Fever and routine check-ups",
                }
            ],
            "appointment_policy": "Arrive 10 minutes early.",
            "cancellation_policy": "Call staff 24 hours before.",
            "emergency_note": "For emergencies, call 108.",
        }
    )

    assert "Email: hello@example.com" in prompt
    assert "Website: https://example.com" in prompt
    assert "- General consultation - fee: 500 rupees" in prompt
    assert "Appointment policy: Arrive 10 minutes early." in prompt
    assert "Cancellation policy: Call staff 24 hours before." in prompt
    assert "Emergency note: For emergencies, call 108." in prompt


def test_clinic_formats_only_upcoming_holidays():
    prompt = format_clinic_for_prompt(
        {
            "name": "Test Clinic",
            "holidays": [
                {"date": "2026-10-01", "name": "Past holiday"},
                {"date": "2026-11-08", "name": "Diwali"},
                {"date": "2026-11-10", "name": "Open day", "closed": False},
            ],
        },
        today="2026-11-02",
    )

    assert "Past holiday" not in prompt
    assert "2026-11-08: Diwali (closed)" in prompt
    assert "2026-11-10: Open day (open with special hours)" in prompt


def test_closed_holiday_helper_matches_only_closed_dates():
    profile = ClinicProfile.model_validate(
        {
            "name": "Test Clinic",
            "holidays": [
                ClinicHoliday(date="2026-11-08", name="Diwali"),
                ClinicHoliday(
                    date="2026-11-10", name="Open day", closed=False
                ),
            ],
        }
    )

    assert closed_holiday_for_date(profile, date(2026, 11, 8)).name == "Diwali"
    assert closed_holiday_for_date(profile, date(2026, 11, 10)) is None
    assert closed_holiday_for_date(profile, date(2026, 11, 9)) is None


def test_clinic_profile_rejects_invalid_contact_details():
    with pytest.raises(ValidationError):
        ClinicProfile.model_validate(
            {"name": "Test Clinic", "email": "not-an-email"}
        )
    with pytest.raises(ValidationError):
        ClinicProfile.model_validate(
            {"name": "Test Clinic", "website": "example.com"}
        )


def test_day_bounds_cover_clinic_timezone_day():
    start_at, end_at = day_bounds_utc(date(2026, 11, 2))

    assert start_at.isoformat() == "2026-11-01T18:30:00+00:00"
    assert end_at.isoformat() == "2026-11-02T18:30:00+00:00"


def test_build_query_filters_status_doctor_and_date():
    query = build_query(
        status="confirmed",
        doctor="Dr. Sharma",
        date_value="2026-11-02",
    )

    assert query["status"] == "confirmed"
    assert query["doctor_name"]["$options"] == "i"
    assert "$gte" in query["start_at"]
    assert "$lt" in query["start_at"]
