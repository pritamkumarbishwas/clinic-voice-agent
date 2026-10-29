from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.api.routes import analytics as analytics_route
from app.api.routes import appointments as appointments_route
from app.api.routes import calls as calls_route
from app.api.routes import doctors as doctors_route
from app.api.routes import health as health_route
from app.api.routes import voice as voice_route
from app.auth import CurrentUser, get_optional_user, require_admin
from app.core.errors import ApiError
from app.main import create_app
from app.services import (
    analytics_service,
    appointment_api_service,
    voice_session_service,
)

ADMIN = CurrentUser(
    id="admin-id",
    email="admin@example.com",
    name="Admin",
    role="admin",
)


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[require_admin] = lambda: ADMIN
    test_client = TestClient(app)
    yield test_client
    test_client.close()


@pytest.fixture
def anonymous_client():
    app = create_app()
    test_client = TestClient(app)
    yield test_client
    test_client.close()


def test_root_and_versioned_health_routes(monkeypatch, client):
    async def ready():
        return True

    monkeypatch.setattr(health_route, "database_ready", ready)

    for path in ("/health", "/api/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["database"] == "ok"


def test_public_doctors_list_and_admin_inactive_guard(
    monkeypatch, client
):
    async def fake_list_doctors(include_inactive=False):
        return [
            {
                "doctor_id": "doc-1",
                "name": "Dr. Meera",
                "specialty": "General",
                "active": not include_inactive,
            }
        ]

    monkeypatch.setattr(doctors_route, "list_doctors", fake_list_doctors)

    response = client.get("/api/v1/doctors")
    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "Dr. Meera"

    forbidden = client.get("/api/v1/doctors?include_inactive=true")
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    client.app.dependency_overrides[get_optional_user] = lambda: ADMIN
    allowed = client.get("/api/v1/doctors?include_inactive=true")
    assert allowed.status_code == 200


def test_availability_is_public_and_errors_are_structured(
    monkeypatch, client
):
    async def available(date_value, doctor):
        return {
            "ok": True,
            "doctor": doctor,
            "date": date_value,
            "slots": [],
            "message": "Only offer these slot_id values.",
        }

    monkeypatch.setattr(
        appointments_route,
        "check_availability",
        available,
    )
    response = client.get(
        "/api/v1/appointments/availability",
        params={"date": "2026-10-30", "doctor": "Dr. Meera"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "No available slots on that date."

    async def missing(date_value, doctor):
        return {
            "ok": False,
            "code": "DOCTOR_NOT_FOUND",
            "message": "internal voice wording",
        }

    monkeypatch.setattr(
        appointments_route,
        "check_availability",
        missing,
    )
    response = client.get(
        "/api/v1/appointments/availability",
        params={"date": "2026-10-30", "doctor": "Nobody"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCTOR_NOT_FOUND"
    assert response.json()["detail"] == "Doctor not found."


def test_public_booking_and_idempotent_replay(monkeypatch, client):
    calls = []

    async def fake_create(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "appointment_id": "appt-1",
            "reference": "CLN-ABC123",
            "doctor": "Dr. Meera",
            "idempotency_key": kwargs["idempotency_key"],
            "idempotent_replay": False,
        }

    monkeypatch.setattr(
        appointments_route,
        "api_create_appointment",
        fake_create,
    )

    response = client.post(
        "/api/v1/appointments",
        headers={"Idempotency-Key": "idem-12345"},
        json={
            "name": "Asha",
            "phone": "9876543210",
            "slot_id": "slot-1",
        },
    )
    assert response.status_code == 201
    assert response.json()["reference"] == "CLN-ABC123"
    assert calls[0]["idempotency_key"] == "idem-12345"

    async def replay(**kwargs):
        return {
            "ok": True,
            "appointment_id": "appt-1",
            "reference": "CLN-ABC123",
            "idempotency_key": kwargs["idempotency_key"],
            "idempotent_replay": True,
        }

    monkeypatch.setattr(
        appointments_route,
        "api_create_appointment",
        replay,
    )
    response = client.post(
        "/api/v1/appointments",
        headers={"Idempotency-Key": "idem-12345"},
        json={
            "name": "Asha",
            "phone": "9876543210",
            "slot_id": "slot-1",
        },
    )
    assert response.status_code == 200
    assert response.json()["idempotent_replay"] is True


def test_booking_rejects_invalid_voice_session_token(client):
    response = client.post(
        "/api/v1/appointments",
        headers={"X-Voice-Session": "not-a-token"},
        json={
            "name": "Asha",
            "phone": "9876543210",
            "slot_id": "slot-1",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SESSION_TOKEN"


def test_booking_accepts_valid_voice_session_token(monkeypatch, client):
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return {
            "ok": True,
            "appointment_id": "appt-1",
            "reference": "CLN-ABC123",
            "idempotent_replay": False,
        }

    monkeypatch.setattr(
        appointments_route,
        "api_create_appointment",
        fake_create,
    )
    token = voice_session_service.create_session_token("clinic-room")
    response = client.post(
        "/api/v1/appointments",
        headers={
            "Idempotency-Key": "idem-12345",
            "X-Voice-Session": token,
        },
        json={
            "name": "Asha",
            "phone": "9876543210",
            "slot_id": "slot-1",
        },
    )
    assert response.status_code == 201
    assert captured["voice_session_room"] == "clinic-room"


def test_admin_appointment_list_update_and_cancel(
    monkeypatch, client
):
    async def fake_list(**kwargs):
        return {
            "items": [],
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
            "total": 0,
            "total_pages": 1,
        }

    async def fake_reschedule(appointment_id, *, new_slot_id):
        return {
            "ok": True,
            "appointment_id": appointment_id,
            "status": "confirmed",
            "local_time": new_slot_id,
        }

    async def fake_cancel(appointment_id):
        return {
            "ok": True,
            "appointment_id": appointment_id,
            "status": "cancelled",
        }

    monkeypatch.setattr(
        appointments_route,
        "db_list_appointments",
        fake_list,
    )
    monkeypatch.setattr(
        appointments_route,
        "reschedule_appointment_by_id",
        fake_reschedule,
    )
    monkeypatch.setattr(
        appointments_route,
        "cancel_appointment_by_id",
        fake_cancel,
    )

    assert client.get("/api/v1/appointments").status_code == 200
    patched = client.patch(
        "/api/v1/appointments/appt-1",
        json={"slot_id": "slot-2"},
    )
    assert patched.status_code == 200
    assert patched.json()["local_time"] == "slot-2"

    cancelled = client.post("/api/v1/appointments/appt-1/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_appointment_admin_routes_require_login(anonymous_client):
    assert anonymous_client.get("/api/v1/appointments").status_code == 401
    assert (
        anonymous_client.patch(
            "/api/v1/appointments/appt-1",
            json={"slot_id": "slot-2"},
        ).status_code
        == 401
    )
    assert (
        anonymous_client.post(
            "/api/v1/appointments/appt-1/cancel"
        ).status_code
        == 401
    )


def test_call_transcript_is_paginated_and_no_store(
    monkeypatch, client
):
    async def fake_transcript(call_id, page=1, page_size=200):
        return {
            "call_id": call_id,
            "items": [{"role": "user", "text": "hello"}],
            "page": page,
            "page_size": page_size,
            "total": 1,
            "total_pages": 1,
        }

    monkeypatch.setattr(
        calls_route.calls_repository,
        "get_call_transcript",
        fake_transcript,
    )
    response = client.get(
        "/api/v1/calls/call-1/transcript",
        params={"page": 2, "page_size": 10},
    )
    assert response.status_code == 200
    assert response.json()["page"] == 2
    assert response.headers["cache-control"] == "no-store"

    async def missing(call_id, page=1, page_size=200):
        return None

    monkeypatch.setattr(
        calls_route.calls_repository,
        "get_call_transcript",
        missing,
    )
    assert (
        client.get("/api/v1/calls/missing/transcript").status_code
        == 404
    )


def test_analytics_summary_endpoint(monkeypatch, client):
    async def fake_summary(**kwargs):
        return {
            "range": {
                "from_date": "2026-10-01",
                "to_date": "2026-10-29",
                "run_id": None,
            },
            "calls": {
                "total": 2,
                "completed": 2,
                "average_duration_seconds": 30.0,
                "by_outcome": {"booked": 1},
                "by_sentiment": {"positive": 2},
            },
            "appointments": {
                "total": 1,
                "by_status": {"confirmed": 1},
            },
            "booking_conversion_rate": 0.5,
            "latency": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    monkeypatch.setattr(
        analytics_route,
        "get_analytics_summary",
        fake_summary,
    )
    response = client.get(
        "/api/v1/analytics",
        params={"from": "2026-10-01", "to": "2026-10-29"},
    )
    assert response.status_code == 200
    assert response.json()["calls"]["total"] == 2


def test_voice_session_endpoint(monkeypatch, client):
    async def fake_session(run_id, request):
        return {
            "server_url": "wss://example.livekit.cloud",
            "token": "livekit-token",
            "room_name": "clinic-room",
            "identity": "patient-1",
            "run_id": run_id,
            "session_token": "session-token",
            "expires_in": 900,
        }

    monkeypatch.setattr(
        voice_route,
        "create_voice_session",
        fake_session,
    )
    response = client.post("/api/v1/voice/session", json={})
    assert response.status_code == 200
    assert response.json()["room_name"] == "clinic-room"
    assert response.json()["session_token"] == "session-token"


def test_error_handler_preserves_detail_and_adds_structure(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.headers["x-request-id"]

    validation = client.post(
        "/api/v1/appointments",
        headers={"Idempotency-Key": "idem-12345"},
        json={"phone": "9876543210", "slot_id": "slot-1"},
    )
    assert validation.status_code == 422
    assert validation.json()["error"]["code"] == "VALIDATION_ERROR"
    assert validation.json()["detail"]


def test_voice_session_token_round_trip_and_invalid_token():
    token = voice_session_service.create_session_token("clinic-room")
    payload = voice_session_service.decode_session_token(token)
    assert payload["scope"] == "voice_session"
    assert payload["room_name"] == "clinic-room"

    with pytest.raises(ApiError) as error:
        voice_session_service.decode_session_token("bad-token")
    assert error.value.status_code == 401


def test_livekit_token_requires_configuration(monkeypatch):
    fake_settings = SimpleNamespace(
        livekit_url="",
        livekit_api_key="",
        livekit_api_secret="",
    )
    monkeypatch.setattr(
        voice_session_service,
        "settings",
        fake_settings,
    )
    with pytest.raises(ApiError) as error:
        import asyncio

        asyncio.run(
            voice_session_service.create_livekit_token(None, None)
        )
    assert error.value.status_code == 503


def test_appointment_service_generates_key_for_blank_idempotency(
    monkeypatch,
):
    captured = {}

    async def find_none(query):
        captured["query"] = query
        return None

    async def fake_book(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "reference": "CLN-ABC123"}

    monkeypatch.setattr(
        appointment_api_service.appointments,
        "find_one",
        find_none,
    )
    monkeypatch.setattr(
        appointment_api_service,
        "book_appointment",
        fake_book,
    )
    result = asyncio_run(
        appointment_api_service.create_appointment(
            name="Asha",
            phone="9876543210",
            slot_id="slot-1",
            idempotency_key="        ",
        )
    )
    key = result["idempotency_key"]
    assert key.startswith("api-")
    assert captured["extra_fields"]["api_idempotency_key"] == key


def test_appointment_idempotency_service_replays_and_conflicts(
    monkeypatch,
):
    fingerprint = appointment_api_service._fingerprint(
        "Asha", "9876543210", "slot-1"
    )
    existing = {
        "_id": ObjectId(),
        "reference": "CLN-ABC123",
        "doctor_name": "Dr. Meera",
        "name": "Asha",
        "start_at": datetime.now(timezone.utc),
        "status": "confirmed",
        "api_idempotency_fingerprint": fingerprint,
    }

    async def find_existing(query):
        return existing

    monkeypatch.setattr(
        appointment_api_service.appointments,
        "find_one",
        find_existing,
    )
    result = asyncio_run(
        appointment_api_service.create_appointment(
            name="Asha",
            phone="9876543210",
            slot_id="slot-1",
            idempotency_key="idem-12345",
        )
    )
    assert result["idempotent_replay"] is True

    async def find_conflict(query):
        return {**existing, "api_idempotency_fingerprint": "different"}

    monkeypatch.setattr(
        appointment_api_service.appointments,
        "find_one",
        find_conflict,
    )
    result = asyncio_run(
        appointment_api_service.create_appointment(
            name="Asha",
            phone="9876543210",
            slot_id="slot-1",
            idempotency_key="idem-12345",
        )
    )
    assert result["code"] == "IDEMPOTENCY_CONFLICT"


def test_analytics_builder_and_range_validation():
    summary = analytics_service._build_summary(
        from_date=date(2026, 10, 1),
        to_date=date(2026, 10, 29),
        run_id=None,
        call_row={
            "total": 4,
            "completed": 3,
            "booked": 2,
            "cancelled": 0,
            "not_booked": 1,
            "positive": 2,
            "neutral": 1,
            "negative": 0,
            "unknown": 0,
            "avg_duration_ms": 45000,
        },
        appointment_rows=[
            {"_id": "confirmed", "count": 2},
            {"_id": "cancelled", "count": 1},
        ],
        turn_row={
            "turn_count": 8,
            "avg_llm_latency_ms": 120.456,
            "avg_tts_latency_ms": 90,
        },
    )
    assert summary["calls"]["total"] == 4
    assert summary["calls"]["average_duration_seconds"] == 45.0
    assert summary["appointments"]["total"] == 3
    assert summary["booking_conversion_rate"] == 0.5
    assert summary["latency"]["average_ms"]["llm"] == 120.46

    with pytest.raises(ApiError) as error:
        asyncio_run(
            analytics_service.get_analytics_summary(
                from_date=date(2026, 10, 29),
                to_date=date(2026, 10, 1),
            )
        )
    assert error.value.status_code == 422

    with pytest.raises(ApiError) as error:
        asyncio_run(
            analytics_service.get_analytics_summary(
                from_date=date(2025, 1, 1),
                to_date=date(2026, 1, 2),
            )
        )
    assert error.value.code == "DATE_RANGE_TOO_LARGE"


def asyncio_run(coroutine):
    import asyncio

    return asyncio.run(coroutine)
