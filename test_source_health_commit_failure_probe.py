"""Current broad-tree probe for fetch-health vs durable-ingestion truth."""
import pytest

import app
import preload
import source_runtime
from source_health import get_source_cursor, source_health_snapshot


def _point_db(monkeypatch, tmp_path):
    path = tmp_path / "source-health-commit-failure.db"
    monkeypatch.setattr(app, "DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    app.init_db()
    return path


def _ted_row():
    return {
        "publication-number": "443-2026",
        "publication-date": "2026-08-27",
        "notice-title": "Source health commit failure probe",
        "buyer-country": "PRT",
    }


def _ted_health(conn):
    items = [item for item in source_health_snapshot(conn) if item["source"] == "TED"]
    assert len(items) == 1
    return items[0]


def test_fetch_success_cannot_remain_current_ingestion_truth_after_commit_failure(monkeypatch, tmp_path):
    _point_db(monkeypatch, tmp_path)
    source_runtime.discard_staged_source_syncs()
    monkeypatch.setattr(preload, "_fetch_ted_resilient", lambda: [_ted_row()])

    rows = preload._fetch_ted_with_health()
    assert len(rows) == 1

    conn = app.db()
    try:
        before = _ted_health(conn)
        assert before["status"] == "healthy"
        assert before["health"] == "healthy"
        assert get_source_cursor(conn, "TED") is None

        def fail_metadata(*_args, **_kwargs):
            raise RuntimeError("synthetic canonical commit failure")

        monkeypatch.setattr(source_runtime, "persist_source_metadata", fail_metadata)
        with pytest.raises(RuntimeError, match="synthetic canonical commit failure"):
            source_runtime.commit_staged_source_syncs(conn)

        assert get_source_cursor(conn, "TED") is None
        after = _ted_health(conn)
        assert after["status"] != "healthy", (
            "FETCH_SUCCESS_OUTLIVED_FAILED_INGESTION: fetch observation remains healthy "
            "after canonical source commit failed and no cursor became durable"
        )
        assert after["health"] == "degraded"
        assert after["stats_state"] == "stale"
        assert after["last_error"] == "ingestion_commit_failed:RuntimeError"
    finally:
        conn.close()
        source_runtime.discard_staged_source_syncs()
