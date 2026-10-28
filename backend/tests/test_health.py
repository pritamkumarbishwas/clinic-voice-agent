import pytest
from fastapi import HTTPException

from app.api.routes import health


async def test_liveness_check_does_not_touch_database(monkeypatch):
    async def fail_if_called():
        raise AssertionError("liveness must not query MongoDB")

    monkeypatch.setattr(health, "database_ready", fail_if_called)

    assert await health.liveness_check() == {
        "status": "alive",
        "service": "clinic-voice-agent",
    }


async def test_health_check_reports_database_unavailable(monkeypatch):
    async def not_ready():
        return False

    monkeypatch.setattr(health, "database_ready", not_ready)

    with pytest.raises(HTTPException) as error:
        await health.health_check()

    assert error.value.status_code == 503
    assert error.value.detail == "Database unavailable"


async def test_health_and_readiness_report_healthy(monkeypatch):
    async def ready():
        return True

    monkeypatch.setattr(health, "database_ready", ready)

    expected = {
        "status": "healthy",
        "service": "clinic-voice-agent",
        "database": "ok",
    }
    assert await health.health_check() == expected
    assert await health.readiness_check() == expected
