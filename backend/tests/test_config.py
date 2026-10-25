from app.config import sanitize_run_id


def test_sanitize_run_id_accepts_safe_values():
    assert sanitize_run_id("baseline-1") == "baseline-1"
    assert sanitize_run_id(" baseline 1 ") == "baseline 1"
    assert sanitize_run_id("run_2026-10") == "run_2026-10"


def test_sanitize_run_id_rejects_unsafe_values():
    assert sanitize_run_id("") is None
    assert sanitize_run_id("   ") is None
    assert sanitize_run_id("bad/slash") is None
    assert sanitize_run_id("x" * 49) is None
    assert sanitize_run_id(None) is None
