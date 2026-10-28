import pytest

from app.services.booking_session import (
    BookingSessionState,
    BookingStateLockedError,
    normalize_iso_date,
)


def _available_result():
    return {
        "ok": True,
        "doctor": "Dr. Sharma",
        "date": "2026-10-29",
        "slots": [
            {
                "slot_id": "slot-1",
                "doctor": "Dr. Sharma",
                "local_time": "10:00 AM",
            },
            {
                "slot_id": "slot-2",
                "doctor": "Dr. Sharma",
                "local_time": "10:30 AM",
            },
        ],
    }


def test_empty_state_summary_says_nothing_captured():
    summary = BookingSessionState().prompt_summary()

    assert "No booking details have been captured yet." in summary


def test_update_details_renders_captured_values():
    state = BookingSessionState()

    state.update_details(
        date="2026-10-29",
        doctor="Dr. Sharma",
        name="Priya Sharma",
        phone="+91 98765 43210",
    )
    summary = state.prompt_summary()

    assert "Requested date: Thursday, 2026-10-29" in summary
    assert "Selected doctor: Dr. Sharma" in summary
    assert "Patient name: Priya Sharma" in summary
    assert "Phone: +91 98765 43210" in summary
    assert "Captured details: date, doctor, patient name, phone number." in summary
    assert "Do not ask for these again." in summary


def test_update_details_rejects_invalid_date():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        BookingSessionState().update_details(date="kal")


def test_normalize_iso_date_accepts_whitespace_and_devanagari_digits():
    assert normalize_iso_date(" 2026-10-29 ") == "2026-10-29"
    assert normalize_iso_date("२०२६-१०-२९") == "2026-10-29"


def test_date_change_invalidates_availability_and_slot():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")
    state.record_availability(_available_result())
    state.record_booking_attempt(
        name="Priya Sharma",
        phone="9876543210",
        slot_id="slot-1",
        local_time="10:00 AM",
    )

    state.update_details(date="2026-10-30")

    assert state.requested_date == "2026-10-30"
    assert state.doctor == "Dr. Sharma"
    assert state.availability_status == "not_checked"
    assert state.available_slots == []
    assert state.selected_slot_id is None
    assert state.selected_time is None
    assert state.patient_name == "Priya Sharma"
    assert state.phone == "9876543210"


def test_invalid_doctor_does_not_partially_change_date():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")
    state.record_availability(_available_result())

    with pytest.raises(ValueError, match="Doctor name"):
        state.update_details(date="2026-10-30", doctor="")

    assert state.requested_date == "2026-10-29"
    assert state.availability_status == "available"


def test_same_date_keeps_availability():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")
    state.record_availability(_available_result())

    state.update_details(date="2026-10-29")

    assert state.availability_status == "available"
    assert len(state.available_slots) == 2


def test_doctor_correction_invalidates_availability():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")
    state.record_availability(_available_result())

    state.update_details(doctor="Dr. Verma")

    assert state.doctor == "Dr. Verma"
    assert state.availability_status == "not_checked"
    assert state.available_slots == []


def test_availability_with_no_slots_is_unavailable():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")

    state.record_availability(
        {
            "ok": True,
            "doctor": "Dr. Sharma",
            "date": "2026-10-29",
            "slots": [],
        }
    )

    assert state.availability_status == "unavailable"
    assert "Availability: no slots available" in state.prompt_summary()


def test_availability_records_canonical_doctor_and_slots():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Sharma")

    state.record_availability(_available_result())

    assert state.doctor == "Dr. Sharma"
    assert state.availability_status == "available"
    assert [slot["local_time"] for slot in state.available_slots] == [
        "10:00 AM",
        "10:30 AM",
    ]
    assert "Availability: available (10:00 AM, 10:30 AM)" in state.prompt_summary()


def test_closed_clinic_is_unavailable():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")

    state.record_availability(
        {
            "ok": False,
            "code": "CLINIC_CLOSED",
            "date": "2026-10-29",
            "slots": [],
        }
    )

    assert state.availability_status == "unavailable"
    assert state.last_error_code == "CLINIC_CLOSED"


def test_unknown_doctor_is_cleared():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")

    state.record_availability(
        {"ok": False, "code": "DOCTOR_NOT_FOUND"}
    )

    assert state.doctor is None
    assert state.availability_status == "error"


def test_availability_error_does_not_claim_slots():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")

    state.record_availability_error()

    assert state.availability_status == "error"
    assert state.available_slots == []
    assert "could not be verified" in state.prompt_summary()


def test_verified_booking_confirms_state():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")
    state.record_availability(_available_result())
    state.record_booking_attempt(
        name="Priya Sharma",
        phone="9876543210",
        slot_id="slot-1",
        local_time="10:00 AM",
    )

    state.record_booking(
        {
            "ok": True,
            "appointment_id": "appointment-1",
            "doctor": "Dr. Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
        }
    )

    assert state.is_confirmed
    assert state.appointment_id == "appointment-1"
    assert "Booking status: confirmed" in state.prompt_summary()
    assert "Do not collect booking details again" in state.prompt_summary()


def test_confirmed_booking_rejects_detail_changes():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")
    state.record_booking_attempt(
        name="Priya Sharma",
        phone="9876543210",
        slot_id="slot-1",
    )
    state.record_booking({"ok": True, "appointment_id": "appointment-1"})

    with pytest.raises(BookingStateLockedError):
        state.update_details(phone="9999999999")


def test_slot_unavailable_clears_slot_for_recheck():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")
    state.record_availability(_available_result())
    state.record_booking_attempt(
        name="Priya Sharma",
        phone="9876543210",
        slot_id="slot-1",
        local_time="10:00 AM",
    )

    state.record_booking(
        {"ok": False, "code": "SLOT_UNAVAILABLE"}
    )

    assert not state.is_confirmed
    assert state.availability_status == "not_checked"
    assert state.available_slots == []
    assert state.selected_slot_id is None
    assert state.patient_name == "Priya Sharma"
    assert state.phone == "9876543210"


def test_booking_failure_keeps_details_for_safe_retry():
    state = BookingSessionState()
    state.update_details(date="2026-10-29", doctor="Dr. Sharma")
    state.record_booking_attempt(
        name="Priya Sharma",
        phone="9876543210",
        slot_id="slot-1",
    )

    state.record_booking_error()

    assert state.booking_status == "failed"
    assert state.selected_slot_id == "slot-1"
    assert "not confirmed" in state.prompt_summary()
