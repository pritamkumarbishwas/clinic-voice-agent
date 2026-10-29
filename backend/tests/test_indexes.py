import asyncio

from pymongo.errors import OperationFailure

from app.db import indexes


class FakeAppointments:
    def __init__(self, information, *, drop_failure=False):
        self.information = information
        self.drop_failure = drop_failure
        self.dropped = []
        self.created = None

    async def index_information(self):
        return self.information

    async def drop_index(self, name):
        if self.drop_failure:
            raise OperationFailure("index permission denied")
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


def test_legacy_index_drop_failure_does_not_crash_startup(monkeypatch):
    fake = FakeAppointments(
        {
            "slot_id_1": {
                "key": [("slot_id", 1)],
                "unique": True,
            }
        },
        drop_failure=True,
    )
    monkeypatch.setattr(indexes, "appointments", fake)

    asyncio.run(indexes._ensure_appointment_slot_index())

    assert fake.dropped == []
    keys, options = fake.created
    assert keys == [("slot_id", 1)]
    assert options["partialFilterExpression"] == {"status": "confirmed"}


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


def test_appointment_idempotency_index_is_unique_and_partial(monkeypatch):
    fake = FakeAppointments({})
    monkeypatch.setattr(indexes, "appointments", fake)

    asyncio.run(indexes._ensure_appointment_idempotency_index())

    keys, options = fake.created
    assert keys == [("api_idempotency_key", 1)]
    assert options["unique"] is True
    assert options["name"] == indexes.APPOINTMENT_IDEMPOTENCY_INDEX
    assert options["partialFilterExpression"] == {
        "api_idempotency_key": {"$type": "string"}
    }
