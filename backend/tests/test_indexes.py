import asyncio

from app.db import indexes


class FakeAppointments:
    def __init__(self, information):
        self.information = information
        self.dropped = []
        self.created = None

    async def index_information(self):
        return self.information

    async def drop_index(self, name):
        self.dropped.append(name)

    async def create_index(self, keys, **options):
        self.created = (keys, options)


def test_legacy_unique_slot_index_is_replaced(monkeypatch):
    fake = FakeAppointments(
        {
            "slot_id_1": {
                "key": [("slot_id", 1)],
                "unique": True,
            }
        }
    )
    monkeypatch.setattr(indexes, "appointments", fake)

    asyncio.run(indexes._ensure_appointment_slot_index())

    assert fake.dropped == ["slot_id_1"]
    keys, options = fake.created
    assert keys == [("slot_id", 1)]
    assert options["unique"] is True
    assert options["partialFilterExpression"] == {"status": "confirmed"}
    assert options["name"] == indexes.APPOINTMENT_SLOT_INDEX


def test_confirmed_only_slot_index_is_kept(monkeypatch):
    fake = FakeAppointments(
        {
            indexes.APPOINTMENT_SLOT_INDEX: {
                "key": [("slot_id", 1)],
                "unique": True,
                "partialFilterExpression": {"status": "confirmed"},
            }
        }
    )
    monkeypatch.setattr(indexes, "appointments", fake)

    asyncio.run(indexes._ensure_appointment_slot_index())

    assert fake.dropped == []
    keys, options = fake.created
    assert keys == [("slot_id", 1)]
    assert options["partialFilterExpression"] == {"status": "confirmed"}
