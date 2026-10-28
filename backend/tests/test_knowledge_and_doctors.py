from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.services.doctor_service import (
    DoctorProfile,
    _slot_datetimes_for_doctor,
)
from app.services.embedding_service import cosine_similarity
from app.services.knowledge_service import (
    chunk_text,
    guess_title_from_filename,
    normalize_category,
)


def test_chunk_text_keeps_short_content_as_one_chunk():
    assert chunk_text("Short clinic answer.") == ["Short clinic answer."]
    assert chunk_text("  ") == []


def test_chunk_text_splits_long_content_with_overlap():
    text = " ".join(f"Sentence {index} about the clinic." for index in range(80))
    chunks = chunk_text(text, max_chars=200, overlap=40)

    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)
    assert "Sentence 0 about the clinic." in chunks[0]


def test_cosine_similarity_handles_vectors_and_edge_cases():
    assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine_similarity([1, 0], [1, 0, 0]) == 0.0
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([0, 0], [1, 1]) == 0.0


def test_knowledge_helpers_normalize_admin_input():
    assert normalize_category(" Services ") == "services"
    assert normalize_category("unknown") == "general"
    assert guess_title_from_filename("parking_faq.md") == "parking faq"
    assert guess_title_from_filename(".txt") == "Uploaded clinic knowledge"


def test_doctor_profile_validates_schedule():
    doctor = DoctorProfile.model_validate(
        {
            "name": "Dr. Rao",
            "languages": ["Hindi", "Hindi", " English "],
            "working_days": [5, 1, 1],
            "start_time": "10:00",
            "end_time": "13:00",
            "slot_minutes": 30,
        }
    )

    assert doctor.languages == ["Hindi", "English"]
    assert doctor.working_days == [1, 5]

    with pytest.raises(ValidationError):
        DoctorProfile.model_validate(
            {
                "name": "Dr. Rao",
                "start_time": "14:00",
                "end_time": "13:00",
            }
        )
    with pytest.raises(ValidationError):
        DoctorProfile.model_validate(
            {"name": "Dr. Rao", "working_days": [7]}
        )


def test_slot_generation_respects_working_days_and_hours():
    doctor = DoctorProfile.model_validate(
        {
            "name": "Dr. Rao",
            "working_days": [0, 2],
            "start_time": "10:00",
            "end_time": "11:00",
            "slot_minutes": 30,
        }
    )
    starts = _slot_datetimes_for_doctor(doctor, date(2026, 11, 2), 7)
    local = [
        start.astimezone(ZoneInfo("Asia/Kolkata")).isoformat()
        for start in starts
    ]

    assert local == [
        "2026-11-02T10:00:00+05:30",
        "2026-11-02T10:30:00+05:30",
        "2026-11-04T10:00:00+05:30",
        "2026-11-04T10:30:00+05:30",
    ]
    assert all(
        isinstance(start, datetime) and start.tzinfo is not None
        for start in starts
    )
