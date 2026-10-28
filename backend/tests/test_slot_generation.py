from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from bson import ObjectId

from app.services import doctor_service


class FakeSlots:
    def __init__(self):
        self.operations = None
        self.deleted_query = None

    async def bulk_write(self, operations, ordered=False):
        self.operations = operations
        assert ordered is False

    async def delete_many(self, query):
        self.deleted_query = query
        return SimpleNamespace(deleted_count=2)


async def test_generate_doctor_slots_bulk_writes_and_prunes(monkeypatch):
    doctor_id = ObjectId()
    slot_times = [
        datetime.now(timezone.utc) + timedelta(days=1),
        datetime.now(timezone.utc) + timedelta(days=2),
    ]
    profile = doctor_service.DoctorProfile.model_validate(
        {
            "name": "Dr. Rao",
            "active": True,
            "working_days": [0, 1, 2, 3, 4, 5, 6],
            "start_time": "10:00",
            "end_time": "13:00",
            "slot_minutes": 30,
        }
    )
    fake_slots = FakeSlots()

    async def fake_find_one(query):
        return {"_id": doctor_id, **profile.model_dump()}

    async def fake_clinic_profile():
        return {}

    monkeypatch.setattr(doctor_service.doctors, "find_one", fake_find_one)
    monkeypatch.setattr(doctor_service, "slots", fake_slots)
    monkeypatch.setattr(
        doctor_service, "get_clinic_profile", fake_clinic_profile
    )
    monkeypatch.setattr(
        doctor_service,
        "_slot_datetimes_for_doctor",
        lambda profile, today, days: slot_times,
    )
    monkeypatch.setattr(
        doctor_service, "closed_holiday_for_date", lambda profile, day: False
    )

    result = await doctor_service.generate_doctor_slots(
        str(doctor_id), days=2
    )

    assert result == {"created": 2, "removed": 2}
    assert len(fake_slots.operations) == 2
    assert fake_slots.deleted_query["doctor_id"] == doctor_id
    assert fake_slots.deleted_query["status"] == "available"
    assert len(fake_slots.deleted_query["start_at"]["$nin"]) == 2
