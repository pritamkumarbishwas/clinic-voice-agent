import asyncio
import json

import agent


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

    monkeypatch.setattr(agent, "db_check_availability", fake_check)
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


def test_book_appointment_tool_confirms_only_on_ok(monkeypatch):
    async def fake_book(**kwargs):
        return {
            "ok": True,
            "appointment_id": "appointment-1",
            "doctor": "Dr. Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
        }

    monkeypatch.setattr(agent, "db_book_appointment", fake_book)
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

    monkeypatch.setattr(agent, "db_book_appointment", fake_book)
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
