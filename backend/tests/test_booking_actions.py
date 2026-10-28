import asyncio
import copy
import re
from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.services import booking_service

CLINIC_TZ = booking_service.CLINIC_TZ


def _matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            if "$gt" in expected:
                if actual is None or not actual > expected["$gt"]:
                    return False
            if "$exists" in expected:
                if (key in document) is not expected["$exists"]:
                    return False
            if "$regex" in expected:
                flags = (
                    re.IGNORECASE
                    if expected.get("$options") == "i"
                    else 0
                )
                if not isinstance(actual, str) or not re.search(
                    expected["$regex"], actual, flags
                ):
                    return False
        elif actual != expected:
            return False
    return True


def _apply_update(document: dict, update: dict) -> None:
    for key, value in (update.get("$set") or {}).items():
        document[key] = value


class FakeCollection:
    def __init__(self, documents: list[dict] | None = None):
        self.documents = documents or []
        self.fail_update = False

    async def find_one(self, query, projection=None, session=None):
        for document in self.documents:
            if _matches(document, query):
                return copy.deepcopy(document)
        return None

    async def insert_one(self, document, session=None):
        if "reference" in document:
            for existing in self.documents:
                if existing.get("reference") == document["reference"]:
                    raise PyMongoError("duplicate reference")
        self.documents.append(copy.deepcopy(document))
        return SimpleNamespace(inserted_id=document.get("_id"))

    async def update_one(self, query, update, session=None):
        if self.fail_update:
            raise PyMongoError("simulated update failure")
        for document in self.documents:
            if not _matches(document, query):
                continue
            before = copy.deepcopy(document)
            _apply_update(document, update)
            return SimpleNamespace(
                matched_count=1,
                modified_count=0 if before == document else 1,
            )
        return SimpleNamespace(matched_count=0, modified_count=0)

    async def find_one_and_update(
        self,
        query,
        update,
        return_document=None,
        session=None,
    ):
        for document in self.documents:
            if not _matches(document, query):
                continue
            _apply_update(document, update)
            return copy.deepcopy(document)
        return None


class FakeSession:
    def __init__(self, collections: list[FakeCollection]):
        self._collections = collections

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def with_transaction(self, callback):
        snapshots = [
            (collection, copy.deepcopy(collection.documents))
            for collection in self._collections
        ]
        try:
            return await callback(self)
        except Exception:
            for collection, documents in snapshots:
                collection.documents[:] = documents
            raise


class FakeClient:
    def __init__(self, collections: list[FakeCollection], fail: bool = False):
        self._collections = collections
        self.fail = fail

    async def start_session(self):
        if self.fail:
            raise PyMongoError("database unavailable")
        return FakeSession(self._collections)


def _profile(*, holidays=None) -> dict:
    return {
        "name": "Test Clinic",
        "hours": {
            "open": "10:00",
            "close": "17:00",
            "days": "Monday to Saturday",
        },
        "holidays": holidays or [],
    }


def _slot(
    doctor_id: ObjectId,
    *,
    day_offset: int = 1,
    hour: int = 10,
    minute: int = 0,
    status: str = "available",
    appointment_id: ObjectId | None = None,
) -> dict:
    local_day = (datetime.now(CLINIC_TZ) + timedelta(days=day_offset)).date()
    start_at = datetime.combine(
        local_day,
        time(hour, minute),
        tzinfo=CLINIC_TZ,
    ).astimezone(timezone.utc)
    return {
        "_id": ObjectId(),
        "doctor_id": doctor_id,
        "start_at": start_at,
        "end_at": start_at + timedelta(minutes=30),
        "status": status,
        "appointment_id": appointment_id,
    }


def _appointment(
    *,
    doctor_id: ObjectId,
    slot: dict,
    phone: str = "9876543210",
    status: str = "confirmed",
) -> dict:
    return {
        "_id": ObjectId(),
        "reference": "CLN-ABC234",
        "slot_id": slot["_id"],
        "doctor_id": doctor_id,
        "doctor_name": "Dr. Sharma",
        "name": "Priya Sharma",
        "phone": phone,
        "start_at": slot["start_at"],
        "end_at": slot["end_at"],
        "call_id": "call-1",
        "status": status,
        "created_at": datetime.now(timezone.utc),
    }


def _install(
    monkeypatch,
    *,
    profile: dict | None = None,
    client_fail: bool = False,
):
    appointments = FakeCollection()
    slots = FakeCollection()
    doctors = FakeCollection()
    calls = FakeCollection([{"call_id": "call-1"}])
    collections = [appointments, slots, doctors, calls]

    monkeypatch.setattr(booking_service, "appointments", appointments)
    monkeypatch.setattr(booking_service, "slots", slots)
    monkeypatch.setattr(booking_service, "doctors", doctors)
    monkeypatch.setattr(booking_service, "calls", calls)
    monkeypatch.setattr(
        booking_service,
        "client",
        FakeClient(collections, fail=client_fail),
    )

    async def fake_profile():
        return profile or _profile()

    monkeypatch.setattr(booking_service, "get_clinic_profile", fake_profile)
    return appointments, slots, doctors, calls


def test_generate_booking_reference_is_safe_and_normalizable():
    reference = booking_service.generate_booking_reference()

    assert re.fullmatch(r"CLN-[A-HJ-NP-Z2-9]{6}", reference)
    assert booking_service.normalize_booking_reference(reference) == reference
    assert booking_service.normalize_booking_reference(
        reference.lower().replace("-", " ")
    ) == reference
    assert booking_service.normalize_booking_reference("CLN-O0I1") is None


def test_book_appointment_returns_reference_and_claims_slot(monkeypatch):
    appointments, slots, doctors, calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id)
    slots.documents.append(slot)

    result = asyncio.run(
        booking_service.book_appointment(
            name="Priya Sharma",
            phone="+91 98765 43210",
            slot_id=str(slot["_id"]),
            call_id="call-1",
        )
    )

    assert result["ok"] is True
    assert result["reference"].startswith("CLN-")
    assert len(appointments.documents) == 1
    assert appointments.documents[0]["reference"] == result["reference"]
    assert slots.documents[0]["status"] == "booked"
    assert slots.documents[0]["appointment_id"] == appointments.documents[0]["_id"]
    assert calls.documents[0]["booking_outcome"] == "booked"
    assert calls.documents[0]["appointment_reference"] == result["reference"]


def test_book_appointment_is_idempotent_for_the_same_call(monkeypatch):
    appointments, slots, doctors, _calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id)
    slots.documents.append(slot)

    first = asyncio.run(
        booking_service.book_appointment(
            name="Priya Sharma",
            phone="9876543210",
            slot_id=str(slot["_id"]),
            call_id="call-1",
        )
    )
    second = asyncio.run(
        booking_service.book_appointment(
            name="Priya Sharma",
            phone="9876543210",
            slot_id=str(slot["_id"]),
            call_id="call-1",
        )
    )

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["reference"] == first["reference"]
    assert len(appointments.documents) == 1


def test_book_appointment_allows_rebooking_after_cancellation(monkeypatch):
    appointments, slots, doctors, _calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id)
    slots.documents.append(slot)

    first = asyncio.run(
        booking_service.book_appointment(
            name="Priya Sharma",
            phone="9876543210",
            slot_id=str(slot["_id"]),
            call_id="call-1",
        )
    )
    cancelled = asyncio.run(
        booking_service.cancel_appointment(
            reference=first["reference"],
            phone="9876543210",
            call_id="call-1",
        )
    )
    second = asyncio.run(
        booking_service.book_appointment(
            name="Priya Sharma",
            phone="9876543210",
            slot_id=str(slot["_id"]),
            call_id="call-1",
        )
    )

    assert cancelled["ok"] is True
    assert second["ok"] is True
    assert second["reference"] != first["reference"]
    assert len(appointments.documents) == 2
    assert appointments.documents[0]["status"] == "cancelled"
    assert appointments.documents[1]["status"] == "confirmed"
    assert slots.documents[0]["status"] == "booked"


def test_book_appointment_rejects_slot_outside_clinic_hours(monkeypatch):
    _appointments, slots, doctors, _calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id, hour=18)
    slots.documents.append(slot)

    result = asyncio.run(
        booking_service.book_appointment(
            name="Priya Sharma",
            phone="9876543210",
            slot_id=str(slot["_id"]),
            call_id="call-1",
        )
    )

    assert result["ok"] is False
    assert result["code"] == "SLOT_OUTSIDE_CLINIC_HOURS"


def test_book_appointment_rejects_closed_holiday(monkeypatch):
    doctor_id = ObjectId()
    slot = _slot(doctor_id)
    local_date = slot["start_at"].astimezone(CLINIC_TZ).date().isoformat()
    _appointments, slots, doctors, _calls = _install(
        monkeypatch,
        profile=_profile(
            holidays=[
                {"date": local_date, "name": "Clinic holiday", "closed": True}
            ]
        ),
    )
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slots.documents.append(slot)

    result = asyncio.run(
        booking_service.book_appointment(
            name="Priya Sharma",
            phone="9876543210",
            slot_id=str(slot["_id"]),
            call_id="call-1",
        )
    )

    assert result["ok"] is False
    assert result["code"] == "CLINIC_CLOSED"


def test_book_appointment_rejects_unavailable_slot(monkeypatch):
    _appointments, slots, doctors, _calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id, status="booked")
    slots.documents.append(slot)

    result = asyncio.run(
        booking_service.book_appointment(
            name="Priya Sharma",
            phone="9876543210",
            slot_id=str(slot["_id"]),
            call_id="call-1",
        )
    )

    assert result["ok"] is False
    assert result["code"] == "SLOT_UNAVAILABLE"


def test_book_appointment_returns_safe_error_on_database_failure(monkeypatch):
    _appointments, slots, doctors, _calls = _install(
        monkeypatch,
        client_fail=True,
    )
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id)
    slots.documents.append(slot)

    result = asyncio.run(
        booking_service.book_appointment(
            name="Priya Sharma",
            phone="9876543210",
            slot_id=str(slot["_id"]),
            call_id="call-1",
        )
    )

    assert result["ok"] is False
    assert result["code"] == "BOOKING_ERROR"
    assert slots.documents[0]["status"] == "available"


def test_get_appointment_requires_matching_phone(monkeypatch):
    appointments, slots, doctors, _calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id)
    appointment = _appointment(doctor_id=doctor_id, slot=slot)
    appointments.documents.append(appointment)
    slots.documents.append(slot)

    wrong = asyncio.run(
        booking_service.get_appointment(
            reference="CLN-ABC234",
            phone="9999999999",
        )
    )
    right = asyncio.run(
        booking_service.get_appointment(
            reference="cln abc234",
            phone="98765 43210",
        )
    )

    assert wrong["ok"] is False
    assert wrong["code"] == "APPOINTMENT_NOT_FOUND"
    assert right["ok"] is True
    assert right["reference"] == "CLN-ABC234"


def test_get_appointment_accepts_country_code_variants(monkeypatch):
    appointments, slots, doctors, _calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id)
    appointment = _appointment(
        doctor_id=doctor_id,
        slot=slot,
        phone="+919876543210",
    )
    appointments.documents.append(appointment)
    slots.documents.append(slot)

    result = asyncio.run(
        booking_service.get_appointment(
            reference="CLN-ABC234",
            phone="98765 43210",
        )
    )

    assert result["ok"] is True
    assert result["reference"] == "CLN-ABC234"


def test_cancel_appointment_releases_slot_and_is_idempotent(monkeypatch):
    appointments, slots, doctors, calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id, status="booked")
    appointment = _appointment(doctor_id=doctor_id, slot=slot)
    slot["appointment_id"] = appointment["_id"]
    appointments.documents.append(appointment)
    slots.documents.append(slot)

    first = asyncio.run(
        booking_service.cancel_appointment(
            reference="CLN-ABC234",
            phone="9876543210",
            call_id="call-1",
        )
    )
    second = asyncio.run(
        booking_service.cancel_appointment(
            reference="CLN-ABC234",
            phone="9876543210",
            call_id="call-1",
        )
    )

    assert first["ok"] is True
    assert first["status"] == "cancelled"
    assert second["ok"] is True
    assert "already cancelled" in second["message"]
    assert appointments.documents[0]["status"] == "cancelled"
    assert slots.documents[0]["status"] == "available"
    assert calls.documents[0]["booking_outcome"] == "cancelled"


def test_cancel_appointment_rejects_past_appointment(monkeypatch):
    appointments, slots, doctors, _calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id, day_offset=-1, status="booked")
    appointment = _appointment(doctor_id=doctor_id, slot=slot)
    slot["appointment_id"] = appointment["_id"]
    appointments.documents.append(appointment)
    slots.documents.append(slot)

    result = asyncio.run(
        booking_service.cancel_appointment(
            reference="CLN-ABC234",
            phone="9876543210",
        )
    )

    assert result["ok"] is False
    assert result["code"] == "APPOINTMENT_IN_PAST"
    assert appointments.documents[0]["status"] == "confirmed"


def test_cancel_appointment_returns_safe_error_on_database_failure(monkeypatch):
    appointments, slots, doctors, _calls = _install(
        monkeypatch,
        client_fail=True,
    )
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    slot = _slot(doctor_id, status="booked")
    appointment = _appointment(doctor_id=doctor_id, slot=slot)
    slot["appointment_id"] = appointment["_id"]
    appointments.documents.append(appointment)
    slots.documents.append(slot)

    result = asyncio.run(
        booking_service.cancel_appointment(
            reference="CLN-ABC234",
            phone="9876543210",
        )
    )

    assert result["ok"] is False
    assert result["code"] == "APPOINTMENT_ERROR"
    assert appointments.documents[0]["status"] == "confirmed"
    assert slots.documents[0]["status"] == "booked"


def test_reschedule_appointment_moves_to_same_doctor_slot(monkeypatch):
    appointments, slots, doctors, calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    old_slot = _slot(doctor_id, status="booked")
    new_slot = _slot(doctor_id, day_offset=2, hour=11)
    appointment = _appointment(doctor_id=doctor_id, slot=old_slot)
    old_slot["appointment_id"] = appointment["_id"]
    appointments.documents.append(appointment)
    slots.documents.extend([old_slot, new_slot])

    result = asyncio.run(
        booking_service.reschedule_appointment(
            reference="CLN-ABC234",
            phone="9876543210",
            new_slot_id=str(new_slot["_id"]),
            call_id="call-1",
        )
    )

    assert result["ok"] is True
    assert result["reference"] == "CLN-ABC234"
    assert appointments.documents[0]["slot_id"] == new_slot["_id"]
    assert appointments.documents[0]["start_at"] == new_slot["start_at"]
    assert slots.documents[0]["status"] == "available"
    assert slots.documents[1]["status"] == "booked"
    assert slots.documents[1]["appointment_id"] == appointment["_id"]
    assert calls.documents[0]["booking_outcome"] == "rescheduled"


def test_reschedule_rejects_different_doctor(monkeypatch):
    appointments, slots, doctors, _calls = _install(monkeypatch)
    doctor_id = ObjectId()
    other_doctor_id = ObjectId()
    doctors.documents.extend(
        [
            {"_id": doctor_id, "name": "Dr. Sharma", "active": True},
            {"_id": other_doctor_id, "name": "Dr. Verma", "active": True},
        ]
    )
    old_slot = _slot(doctor_id, status="booked")
    new_slot = _slot(other_doctor_id, day_offset=2, hour=11)
    appointment = _appointment(doctor_id=doctor_id, slot=old_slot)
    old_slot["appointment_id"] = appointment["_id"]
    appointments.documents.append(appointment)
    slots.documents.extend([old_slot, new_slot])

    result = asyncio.run(
        booking_service.reschedule_appointment(
            reference="CLN-ABC234",
            phone="9876543210",
            new_slot_id=str(new_slot["_id"]),
        )
    )

    assert result["ok"] is False
    assert result["code"] == "DOCTOR_MISMATCH"
    assert slots.documents[0]["status"] == "booked"
    assert slots.documents[1]["status"] == "available"


def test_reschedule_rolls_back_if_appointment_update_fails(monkeypatch):
    appointments, slots, doctors, _calls = _install(monkeypatch)
    doctor_id = ObjectId()
    doctors.documents.append(
        {"_id": doctor_id, "name": "Dr. Sharma", "active": True}
    )
    old_slot = _slot(doctor_id, status="booked")
    new_slot = _slot(doctor_id, day_offset=2, hour=11)
    appointment = _appointment(doctor_id=doctor_id, slot=old_slot)
    old_slot["appointment_id"] = appointment["_id"]
    appointments.documents.append(appointment)
    slots.documents.extend([old_slot, new_slot])
    appointments.fail_update = True

    result = asyncio.run(
        booking_service.reschedule_appointment(
            reference="CLN-ABC234",
            phone="9876543210",
            new_slot_id=str(new_slot["_id"]),
        )
    )

    assert result["ok"] is False
    assert result["code"] == "APPOINTMENT_ERROR"
    assert slots.documents[0]["status"] == "booked"
    assert slots.documents[1]["status"] == "available"
    assert appointments.documents[0]["slot_id"] == old_slot["_id"]
