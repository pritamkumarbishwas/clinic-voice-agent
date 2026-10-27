from app.services.booking_service import (
    _clean_text,
    _normalize_doctor_name,
    _normalize_phone,
    format_doctor_roster,
    format_stt_prompt,
)


def test_clean_text_collapses_whitespace():
    assert _clean_text("  Priya   Sharma \n") == "Priya Sharma"


def test_normalize_phone_accepts_common_formatting():
    assert _normalize_phone("+91 98765-43210") == "+919876543210"
    assert _normalize_phone("(98765) 43210") == "9876543210"


def test_normalize_phone_rejects_short_or_non_numeric():
    assert _normalize_phone("12345") is None
    assert _normalize_phone("call me") is None


def test_normalize_phone_converts_devanagari_digits():
    assert _normalize_phone("९८७६५ ४३२१०") == "9876543210"


def test_normalize_doctor_name_strips_prefix():
    assert _normalize_doctor_name("Dr. Sharma") == "Sharma"
    assert _normalize_doctor_name("doctor verma") == "verma"
    assert _normalize_doctor_name("Singh") == "Singh"


def test_format_doctor_roster_lists_names_and_specialties():
    roster = format_doctor_roster(
        [
            {"name": "Dr. Sharma", "specialty": "General Physician"},
            {"name": "Dr. Verma", "specialty": "Dentist"},
            {"name": "", "specialty": "Ignored"},
        ]
    )

    assert roster == (
        "- Dr. Sharma (General Physician)\n"
        "- Dr. Verma (Dentist)"
    )


def test_format_doctor_roster_handles_empty_directory():
    assert format_doctor_roster([]) == "No doctors are configured."


def test_format_stt_prompt_includes_doctor_names():
    prompt = format_stt_prompt(
        [
            {"name": "Dr. Sharma", "specialty": "General Physician"},
            {"name": "Dr. Verma", "specialty": "Dentist"},
            {"name": "", "specialty": "Ignored"},
        ]
    )

    assert "Hindi or Hinglish" in prompt
    assert "Dr. Sharma, Dr. Verma" in prompt


def test_format_stt_prompt_handles_empty_directory():
    prompt = format_stt_prompt([])

    assert "Hindi or Hinglish" in prompt
    assert "Doctors:" not in prompt
