from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.services.appointment_service import build_query, day_bounds_utc
from app.services.clinic_service import ClinicProfile, format_clinic_for_prompt


def test_clinic_prompt_marks_missing_details():
    prompt = format_clinic_for_prompt({"name": "Test Clinic"})

    assert "Clinic name: Test Clinic" in prompt
    assert "Address: Not configured" in prompt
    assert "Opening hours: 10:00 to 17:00 (Mon-Sat)" in prompt


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
