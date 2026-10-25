from app.services.booking_service import (
    _clean_text,
    _normalize_doctor_name,
    _normalize_phone,
)


def test_clean_text_collapses_whitespace():
    assert _clean_text("  Priya   Sharma \n") == "Priya Sharma"


def test_normalize_phone_accepts_common_formatting():
    assert _normalize_phone("+91 98765-43210") == "+919876543210"
    assert _normalize_phone("(98765) 43210") == "9876543210"


def test_normalize_phone_rejects_short_or_non_numeric():
    assert _normalize_phone("12345") is None
    assert _normalize_phone("call me") is None


def test_normalize_doctor_name_strips_prefix():
    assert _normalize_doctor_name("Dr. Sharma") == "Sharma"
    assert _normalize_doctor_name("doctor verma") == "verma"
    assert _normalize_doctor_name("Singh") == "Singh"
