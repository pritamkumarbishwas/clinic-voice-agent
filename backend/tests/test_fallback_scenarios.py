import asyncio
import json

import pytest

import agent
from app.agent import receptionist as receptionist_module
from app.prompts.receptionist import PROMPT_VERSION, build_system_prompt
from app.services.embedding_service import RagUnavailableError

TODAY = "2026-10-29"
CLINIC_DETAILS = "\n".join(
    [
        "Clinic name: Test Clinic",
        "Address: 12 Test Road, Bengaluru 560001",
        "Phone: +91 80 4000 0000",
        "Opening hours: 10:00 to 17:00 (Monday to Saturday)",
        "Consultation fee: 500 rupees",
    ]
)
DOCTOR_ROSTER = "\n".join(
    [
        "- Dr. Sharma (General Physician)",
        "- Dr. Verma (Dentist)",
    ]
)
AVAILABILITY = {
    "ok": True,
    "doctor": "Dr. Sharma",
    "date": TODAY,
    "slots": [{"slot_id": "slot-1", "local_time": "10:00 AM"}],
}


def _prompt(clinic_details: str = CLINIC_DETAILS) -> str:
    return build_system_prompt(
        clinic_name="Test Clinic",
        clinic_details=clinic_details,
        doctor_roster=DOCTOR_ROSTER,
        today=TODAY,
        timezone="Asia/Kolkata",
    )


def _receptionist() -> agent.ClinicReceptionist:
    return agent.ClinicReceptionist(
        "call-1",
        TODAY,
        "Test Clinic",
        CLINIC_DETAILS,
        DOCTOR_ROSTER,
    )


def _available_receptionist() -> agent.ClinicReceptionist:
    receptionist = _receptionist()
    receptionist.booking_state.update_details(
        date=TODAY,
        doctor="Dr. Sharma",
    )
    receptionist.booking_state.record_availability(AVAILABILITY)
    return receptionist


@pytest.mark.parametrize(
    "expected",
    [
        "If you cannot understand the caller's speech, ask them to repeat once.",
        "If speech remains unclear after two attempts",
        "say clinic staff will confirm it",
        "If the caller asks what disease or condition they have",
        "only a qualified clinician can assess it",
        "If the caller asks for a human, offer the configured clinic phone",
        "Never say you have transferred the call",
        "Do not claim success after a tool failure, timeout, or ok=false result.",
        "If a booking or availability tool fails or times out",
        "If knowledge search fails, say clinic staff will confirm.",
        "Never invent a phone number.",
        "Do not invent an address, phone number, fee",
    ],
)
def test_prompt_contains_fallback_policy(expected):
    assert expected in _prompt()


def test_prompt_version_tracks_error_fallback_phase():
    assert PROMPT_VERSION == "phase5-appointment-management-v1"


def test_prompt_handles_missing_phone_without_inventing():
    prompt = _prompt("Clinic name: Test Clinic\nPhone: Not configured")

    assert "If the clinic phone is missing" in prompt
    assert "Never invent a phone number." in prompt
    assert "clinic staff will confirm the next step" in prompt


def test_prompt_keeps_emergency_priority():
    prompt = _prompt()

    assert "call 108 or go to the nearest emergency department" in prompt
    assert "Do not book a routine appointment as a substitute" in prompt


def test_save_booking_details_retains_name_and_phone():
    receptionist = _receptionist()

    asyncio.run(
        receptionist.save_booking_details(
            None,
            "",
            "",
            "Priya Sharma",
            "9876543210",
        )
    )
    asyncio.run(
        receptionist.save_booking_details(
            None,
            TODAY,
            "Dr. Sharma",
            "",
            "",
        )
    )

    assert receptionist.booking_state.patient_name == "Priya Sharma"
    assert receptionist.booking_state.phone == "9876543210"
    assert receptionist.booking_state.requested_date == TODAY
    assert receptionist.booking_state.doctor == "Dr. Sharma"


def test_save_booking_details_accepts_partial_arguments():
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.save_booking_details(
                None,
                name="Priya Sharma",
            )
        )
    )

    assert result["ok"] is True
    assert receptionist.booking_state.patient_name == "Priya Sharma"
    assert receptionist.booking_state.requested_date is None


def test_date_correction_invalidates_availability():
    receptionist = _available_receptionist()

    receptionist.booking_state.update_details(date="2026-10-30")

    assert receptionist.booking_state.availability_status == "not_checked"
    assert receptionist.booking_state.available_slots == []
    assert receptionist.booking_state.selected_slot_id is None


def test_doctor_correction_invalidates_availability():
    receptionist = _available_receptionist()

    receptionist.booking_state.update_details(doctor="Dr. Verma")

    assert receptionist.booking_state.availability_status == "not_checked"
    assert receptionist.booking_state.available_slots == []
    assert receptionist.booking_state.selected_slot_id is None


def test_name_correction_keeps_existing_availability():
    receptionist = _available_receptionist()

    receptionist.booking_state.update_details(name="Priya Verma")

    assert receptionist.booking_state.patient_name == "Priya Verma"
    assert receptionist.booking_state.availability_status == "available"
    assert receptionist.booking_state.available_slots == [
        {"slot_id": "slot-1", "local_time": "10:00 AM"}
    ]


def test_confirmed_booking_locks_detail_changes():
    receptionist = _available_receptionist()
    receptionist.booking_state.record_booking(
        {
            "ok": True,
            "appointment_id": "appointment-1",
            "doctor": "Dr. Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
        }
    )

    result = json.loads(
        asyncio.run(
            receptionist.save_booking_details(
                None,
                "2026-10-30",
                "",
                "",
                "",
            )
        )
    )

    assert result["ok"] is False
    assert result["code"] == "BOOKING_ALREADY_CONFIRMED"
    assert receptionist.booking_state.requested_date == TODAY


def test_confirmed_booking_allows_availability_check_for_reschedule(
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
    receptionist = _available_receptionist()
    receptionist.booking_state.record_booking(
        {
            "ok": True,
            "appointment_id": "appointment-1",
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
    assert receptionist.booking_state.requested_date == TODAY


def test_confirmed_booking_blocks_rebooking():
    receptionist = _available_receptionist()
    receptionist.booking_state.record_booking(
        {
            "ok": True,
            "appointment_id": "appointment-1",
            "doctor": "Dr. Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
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
    assert result["code"] == "BOOKING_ALREADY_CONFIRMED"


def test_invalid_relative_date_is_rejected():
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.save_booking_details(
                None,
                "kal",
                "",
                "",
                "",
            )
        )
    )

    assert result["ok"] is False
    assert result["code"] == "INVALID_BOOKING_DETAIL"
    assert receptionist.booking_state.requested_date is None


def test_doctor_not_found_clears_selected_doctor(monkeypatch):
    async def fake_availability(date, doctor):
        return {
            "ok": False,
            "code": "DOCTOR_NOT_FOUND",
            "message": "Doctor is not available.",
        }

    monkeypatch.setattr(receptionist_module, "db_check_availability", fake_availability)
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.check_availability(
                None,
                TODAY,
                "Dr. Unknown",
            )
        )
    )

    assert result["ok"] is False
    assert receptionist.booking_state.doctor is None
    assert receptionist.booking_state.available_slots == []


def test_no_slots_clears_stale_selection():
    receptionist = _available_receptionist()
    receptionist.booking_state.record_booking_attempt(
        name="Priya Sharma",
        phone="9876543210",
        slot_id="slot-1",
        local_time="10:00 AM",
    )

    receptionist.booking_state.record_availability(
        {
            "ok": True,
            "doctor": "Dr. Sharma",
            "date": TODAY,
            "slots": [],
        }
    )

    assert receptionist.booking_state.availability_status == "unavailable"
    assert receptionist.booking_state.available_slots == []
    assert receptionist.booking_state.selected_slot_id is None


def test_availability_exception_records_error_and_clears_slots(monkeypatch):
    async def fail_availability(date, doctor):
        raise TimeoutError("availability timed out")

    monkeypatch.setattr(receptionist_module, "db_check_availability", fail_availability)
    receptionist = _available_receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.check_availability(
                None,
                TODAY,
                "Dr. Sharma",
            )
        )
    )

    assert result["ok"] is False
    assert result["code"] == "AVAILABILITY_ERROR"
    assert receptionist.booking_state.availability_status == "error"
    assert receptionist.booking_state.available_slots == []


def test_booking_without_confirmation_does_not_call_database(monkeypatch):
    called = False

    async def fake_book(**kwargs):
        nonlocal called
        called = True
        return {"ok": True, "appointment_id": "appointment-1"}

    monkeypatch.setattr(receptionist_module, "db_book_appointment", fake_book)
    receptionist = _available_receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.book_appointment(
                None,
                "Priya Sharma",
                "9876543210",
                "slot-1",
                False,
            )
        )
    )

    assert result["ok"] is False
    assert called is False
    assert receptionist.booking_state.is_confirmed is False


def test_booking_success_confirms_state(monkeypatch):
    async def fake_book(**kwargs):
        return {
            "ok": True,
            "appointment_id": "appointment-1",
            "doctor": "Dr. Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
        }

    monkeypatch.setattr(receptionist_module, "db_book_appointment", fake_book)
    receptionist = _available_receptionist()

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
    assert receptionist.booking_state.is_confirmed is True
    assert receptionist.booking_state.appointment_id == "appointment-1"


def test_booking_failure_does_not_confirm(monkeypatch):
    async def fake_book(**kwargs):
        return {
            "ok": False,
            "code": "BOOKING_FAILED",
            "message": "Booking failed.",
        }

    monkeypatch.setattr(receptionist_module, "db_book_appointment", fake_book)
    receptionist = _available_receptionist()

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
    assert receptionist.booking_state.booking_status == "failed"


def test_slot_unavailable_clears_stale_slot(monkeypatch):
    async def fake_book(**kwargs):
        return {
            "ok": False,
            "code": "SLOT_UNAVAILABLE",
            "message": "That slot is no longer available.",
        }

    monkeypatch.setattr(receptionist_module, "db_book_appointment", fake_book)
    receptionist = _available_receptionist()

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
    assert receptionist.booking_state.availability_status == "not_checked"


def test_booking_rejects_slot_after_date_change(monkeypatch):
    called = False

    async def fake_book(**kwargs):
        nonlocal called
        called = True
        return {"ok": True, "appointment_id": "appointment-1"}

    monkeypatch.setattr(receptionist_module, "db_book_appointment", fake_book)
    receptionist = _available_receptionist()
    receptionist.booking_state.update_details(date="2026-10-30")

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
    assert result["code"] == "INVALID_SLOT"
    assert called is False
    assert receptionist.booking_state.is_confirmed is False


def test_booking_exception_marks_failed_without_success(monkeypatch):
    async def fail_book(**kwargs):
        raise TimeoutError("booking timed out")

    monkeypatch.setattr(receptionist_module, "db_book_appointment", fail_book)
    receptionist = _available_receptionist()

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
    assert result["code"] == "BOOKING_ERROR"
    assert receptionist.booking_state.is_confirmed is False
    assert receptionist.booking_state.booking_status == "failed"


def test_state_summary_does_not_read_internal_error_code():
    receptionist = _receptionist()
    receptionist.booking_state.record_booking_error()

    summary = receptionist.booking_state.prompt_summary()

    assert "BOOKING_ERROR" not in summary
    assert "not confirmed because the booking attempt failed" in summary


def test_search_knowledge_success_returns_results(monkeypatch):
    async def fake_search(query):
        return [
            {
                "title": "Parking",
                "text": "Parking is available behind the clinic.",
            }
        ]

    monkeypatch.setattr(receptionist_module, "search_knowledge", fake_search)
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.search_clinic_knowledge(None, "parking")
        )
    )

    assert result["ok"] is True
    assert result["results"][0]["title"] == "Parking"
    assert "staff will confirm" in result["message"]


def test_search_knowledge_empty_result_uses_staff_confirmation(monkeypatch):
    async def fake_search(query):
        return []

    monkeypatch.setattr(receptionist_module, "search_knowledge", fake_search)
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.search_clinic_knowledge(None, "parking")
        )
    )

    assert result["ok"] is True
    assert result["results"] == []
    assert "staff will confirm" in result["message"]


def test_search_knowledge_unavailable_uses_staff_confirmation(monkeypatch):
    async def fake_search(query):
        raise RagUnavailableError("not configured")

    monkeypatch.setattr(receptionist_module, "search_knowledge", fake_search)
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.search_clinic_knowledge(None, "parking")
        )
    )

    assert result["ok"] is False
    assert "unavailable" in result["message"]
    assert "staff will confirm" in result["message"]


def test_search_knowledge_exception_uses_staff_confirmation(monkeypatch):
    async def fake_search(query):
        raise RuntimeError("provider failed")

    monkeypatch.setattr(receptionist_module, "search_knowledge", fake_search)
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.search_clinic_knowledge(None, "parking")
        )
    )

    assert result["ok"] is False
    assert "failed" in result["message"]
    assert "staff will confirm" in result["message"]


def test_empty_booking_detail_payload_is_rejected():
    receptionist = _receptionist()

    result = json.loads(
        asyncio.run(
            receptionist.save_booking_details(
                None,
                "",
                "",
                "",
                "",
            )
        )
    )

    assert result["ok"] is False
    assert "No booking detail" in result["message"]


def test_booking_uses_exact_returned_slot_id(monkeypatch):
    captured = {}

    async def fake_book(**kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "appointment_id": "appointment-1",
            "doctor": "Dr. Sharma",
            "start_at": "2026-10-29T10:00:00+05:30",
        }

    monkeypatch.setattr(receptionist_module, "db_book_appointment", fake_book)
    receptionist = _available_receptionist()

    asyncio.run(
        receptionist.book_appointment(
            None,
            "Priya Sharma",
            "9876543210",
            "slot-1",
            True,
        )
    )

    assert captured["slot_id"] == "slot-1"
    assert captured["name"] == "Priya Sharma"
    assert captured["phone"] == "9876543210"


def test_booking_failure_preserves_details_for_safe_retry(monkeypatch):
    async def fake_book(**kwargs):
        return {
            "ok": False,
            "code": "BOOKING_FAILED",
            "message": "Booking failed.",
        }

    monkeypatch.setattr(receptionist_module, "db_book_appointment", fake_book)
    receptionist = _available_receptionist()

    asyncio.run(
        receptionist.book_appointment(
            None,
            "Priya Sharma",
            "9876543210",
            "slot-1",
            True,
        )
    )

    assert receptionist.booking_state.patient_name == "Priya Sharma"
    assert receptionist.booking_state.phone == "9876543210"
    assert receptionist.booking_state.selected_slot_id == "slot-1"
    assert receptionist.booking_state.is_confirmed is False


def test_stt_repeat_prompt_asks_for_repeat():
    assert "dobara" in agent.STT_REPEAT_PROMPT
    assert "awaaz" in agent.STT_REPEAT_PROMPT


def test_llm_fallback_does_not_claim_success():
    assert "problem" in agent.LLM_FALLBACK_PROMPT
    assert "book" not in agent.LLM_FALLBACK_PROMPT.lower()

