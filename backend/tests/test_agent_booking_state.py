import asyncio
import json

import agent
from app.agent import receptionist as receptionist_module


def _receptionist() -> agent.ClinicReceptionist:
    return agent.ClinicReceptionist(
        "call-1",
        "2026-10-29",
        "Test Clinic",
        "Clinic name: Test Clinic",
        "- Dr. Sharma (General Physician)",
    )


def test_save_booking_details_tool_updates_session_state():
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.save_booking_details(
                None,
                "2026-10-29",
                "Dr. Sharma",
                "",
                "",
            )
        )
    )

    assert result["ok"] is True
    assert receptionist.booking_state.requested_date == "2026-10-29"
    assert receptionist.booking_state.doctor == "Dr. Sharma"
    assert "Requested date: Thursday, 2026-10-29" in result["session_state"]


def test_user_turn_refresh_adds_captured_state_to_instructions():
    receptionist = _receptionist()
    asyncio.run(
        receptionist.save_booking_details(
            None,
            "2026-10-29",
            "Dr. Sharma",
            "",
            "",
        )
    )

    asyncio.run(receptionist._refresh_instructions())

    assert "Requested date: Thursday, 2026-10-29" in receptionist.instructions
    assert "Selected doctor: Dr. Sharma" in receptionist.instructions


def test_save_booking_details_rejects_relative_date():
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.save_booking_details(None, "kal", "", "", "")
        )
    )

    assert result["ok"] is False
    assert result["code"] == "INVALID_BOOKING_DETAIL"
    assert receptionist.booking_state.requested_date is None


def test_check_availability_tool_records_slots_and_doctor(monkeypatch):
    async def fake_check(date, doctor):
        return {
            "ok": True,
            "doctor": "Dr. Sharma",
            "date": date,
            "slots": [
                {
                    "slot_id": "slot-1",
                    "doctor": "Dr. Sharma",
                    "local_time": "10:00 AM",
                }
            ],
        }

    monkeypatch.setattr(receptionist_module, "db_check_availability", fake_check)
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.check_availability(
                None,
                "2026-10-29",
                "Dr. Sharma",
            )
        )
    )

    assert result["ok"] is True
    assert receptionist.booking_state.availability_status == "available"
    assert receptionist.booking_state.available_slots == [
        {"slot_id": "slot-1", "local_time": "10:00 AM"}
    ]
    assert "Availability: available (10:00 AM)" in result["session_state"]


def test_check_availability_allows_same_doctor_reschedule_after_booking(
    monkeypatch,
):
    async def fake_check(date, doctor):
        return {
            "ok": True,
            "doctor": "Dr. Sharma",
            "date": date,
            "slots": [{"slot_id": "slot-2", "local_time": "11:00 AM"}],
        }

    monkeypatch.setattr(receptionist_module, "db_check_availability", fake_check)
    receptionist = _receptionist()
    receptionist.booking_state.record_booking(
        {
            "ok": True,
            "appointment_id": "appointment-1",
            "reference": "CLN-ABC234",
            "doctor": "Dr. Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
        }
    )

    result = json.loads(
        asyncio.run(
            receptionist.check_availability(
                None,
                "2026-10-30",
                "Dr. Sharma",
            )
        )
    )

    assert result["ok"] is True
    assert result["slots"][0]["slot_id"] == "slot-2"
    assert receptionist.booking_state.is_confirmed
    assert receptionist.booking_state.requested_date == "2026-10-29"


def test_book_appointment_tool_confirms_only_on_ok(monkeypatch):
    async def fake_book(**kwargs):
        return {
            "ok": True,
            "appointment_id": "appointment-1",
            "doctor": "Dr. Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
        }

    monkeypatch.setattr(receptionist_module, "db_book_appointment", fake_book)
    receptionist = _receptionist()
    receptionist.booking_state.update_details(
        date="2026-10-29",
        doctor="Dr. Sharma",
    )
    receptionist.booking_state.record_availability(
        {
            "ok": True,
            "doctor": "Dr. Sharma",
            "date": "2026-10-29",
            "slots": [
                {
                    "slot_id": "slot-1",
                    "local_time": "10:00 AM",
                }
            ],
        }
    )

    result = json.loads(
        asyncio.run(
            receptionist.book_appointment(
                None,
                "Priya Sharma",
                "9876543210",
                "slot-1",
                True,
            )
        )
    )

    assert result["ok"] is True
    assert receptionist.booking_state.is_confirmed
    assert receptionist.booking_state.appointment_id == "appointment-1"
    assert "Booking status: confirmed" in result["session_state"]


def test_book_appointment_tool_does_not_confirm_failed_slot(monkeypatch):
    async def fake_book(**kwargs):
        return {
            "ok": False,
            "code": "SLOT_UNAVAILABLE",
            "message": "That slot is no longer available.",
        }

    monkeypatch.setattr(receptionist_module, "db_book_appointment", fake_book)
    receptionist = _receptionist()
    receptionist.booking_state.update_details(
        date="2026-10-29",
        doctor="Dr. Sharma",
    )
    receptionist.booking_state.record_availability(
        {
            "ok": True,
            "doctor": "Dr. Sharma",
            "date": "2026-10-29",
            "slots": [{"slot_id": "slot-1", "local_time": "10:00 AM"}],
        }
    )

    result = json.loads(
        asyncio.run(
            receptionist.book_appointment(
                None,
                "Priya Sharma",
                "9876543210",
                "slot-1",
                True,
            )
        )
    )

    assert result["ok"] is False
    assert receptionist.booking_state.is_confirmed is False
    assert receptionist.booking_state.selected_slot_id is None
    assert "Booking status: not booked" in result["session_state"]


def test_get_clinic_info_and_doctors_tools(monkeypatch):
    async def fake_profile():
        return {
            "name": "Test Clinic",
            "phone": "+91 80 4000 0000",
            "hours": {"open": "10:00", "close": "17:00"},
        }

    async def fake_doctors():
        return [{"name": "Dr. Sharma", "specialty": "General Physician"}]

    monkeypatch.setattr(receptionist_module, "get_clinic_profile", fake_profile)
    monkeypatch.setattr(
        receptionist_module,
        "get_doctor_directory",
        fake_doctors,
    )
    receptionist = _receptionist()

    clinic = json.loads(
        asyncio.run(receptionist.get_clinic_info(None))
    )
    doctors = json.loads(
        asyncio.run(receptionist.get_doctors(None))
    )

    assert clinic["ok"] is True
    assert clinic["clinic"]["name"] == "Test Clinic"
    assert doctors["ok"] is True
    assert doctors["doctors"][0]["name"] == "Dr. Sharma"


def test_get_appointment_records_verified_lookup_without_confirming(monkeypatch):
    async def fake_lookup(**kwargs):
        return {
            "ok": True,
            "reference": "CLN-ABC234",
            "status": "confirmed",
            "doctor": "Dr. Sharma",
            "name": "Priya Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
        }

    monkeypatch.setattr(receptionist_module, "db_get_appointment", fake_lookup)
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.get_appointment(
                None,
                "CLN-ABC234",
                "9876543210",
            )
        )
    )

    assert result["ok"] is True
    assert receptionist.booking_state.appointment_reference == "CLN-ABC234"
    assert receptionist.booking_state.appointment_status == "confirmed"
    assert receptionist.booking_state.is_confirmed is False
    assert "Appointment reference: CLN-ABC234" in result["session_state"]


def test_cancel_tool_requires_explicit_confirmation(monkeypatch):
    called = False

    async def fake_cancel(**kwargs):
        nonlocal called
        called = True
        return {"ok": True, "reference": "CLN-ABC234", "status": "cancelled"}

    monkeypatch.setattr(
        receptionist_module,
        "db_cancel_appointment",
        fake_cancel,
    )
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.cancel_appointment(
                None,
                "CLN-ABC234",
                "9876543210",
                False,
            )
        )
    )

    assert result["ok"] is False
    assert result["code"] == "CONFIRMATION_REQUIRED"
    assert called is False


def test_cancel_tool_records_verified_cancellation(monkeypatch):
    async def fake_cancel(**kwargs):
        return {
            "ok": True,
            "reference": "CLN-ABC234",
            "status": "cancelled",
        }

    monkeypatch.setattr(
        receptionist_module,
        "db_cancel_appointment",
        fake_cancel,
    )
    receptionist = _receptionist()
    receptionist.booking_state.record_booking(
        {
            "ok": True,
            "appointment_id": "appointment-1",
            "reference": "CLN-ABC234",
            "doctor": "Dr. Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
        }
    )

    result = json.loads(
        asyncio.run(
            receptionist.cancel_appointment(
                None,
                "CLN-ABC234",
                "9876543210",
                True,
            )
        )
    )

    assert result["ok"] is True
    assert receptionist.booking_state.booking_status == "cancelled"
    assert receptionist.booking_state.appointment_status == "cancelled"
    assert receptionist.booking_state.is_confirmed is False
    assert "Booking status: cancelled" in result["session_state"]


def test_reschedule_tool_updates_confirmed_state(monkeypatch):
    async def fake_reschedule(**kwargs):
        return {
            "ok": True,
            "reference": "CLN-ABC234",
            "status": "confirmed",
            "doctor": "Dr. Sharma",
            "name": "Priya Sharma",
            "start_at": "2026-10-30T11:00:00+05:30",
        }

    monkeypatch.setattr(
        receptionist_module,
        "db_reschedule_appointment",
        fake_reschedule,
    )
    receptionist = _receptionist()
    receptionist.booking_state.record_booking(
        {
            "ok": True,
            "appointment_id": "appointment-1",
            "reference": "CLN-ABC234",
            "doctor": "Dr. Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
        }
    )

    result = json.loads(
        asyncio.run(
            receptionist.reschedule_appointment(
                None,
                "CLN-ABC234",
                "9876543210",
                "slot-2",
                True,
            )
        )
    )

    assert result["ok"] is True
    assert receptionist.booking_state.is_confirmed
    assert receptionist.booking_state.requested_date == "2026-10-30"
    assert receptionist.booking_state.selected_time == "11:00 AM"
    assert "Booking status: confirmed" in result["session_state"]

