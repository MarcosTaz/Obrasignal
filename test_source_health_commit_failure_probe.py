"""Current #238 owner-tree probe for fetch-health vs durable-ingestion truth."""
import pytest

import app
import preload
import source_runtime
from source_health import get_source_cursor, source_health_contract


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


def test_fetch_success_cannot_remain_current_ingestion_truth_after_commit_failure(monkeypatch, tmp_path):
    _point_db(monkeypatch, tmp_path)
    source_runtime.discard_staged_source_syncs()
    monkeypatch.setattr(preload, "_fetch_ted_resilient", lambda: [_ted_row()])

    rows = preload._fetch_ted_with_health()
    assert len(rows) == 1

    conn = app.db()
    try:
        before = source_health_contract(conn, sources=["TED"])
        before_item = before["items"][0]
        assert before_item["health"] == "healthy"
        assert before_item["freshness"] == "fresh"
        assert get_source_cursor(conn, "TED") is None

        def fail_metadata(*_args, **_kwargs):
            raise RuntimeError("synthetic canonical commit failure")

        monkeypatch.setattr(source_runtime, "persist_source_metadata", fail_metadata)
        with pytest.raises(RuntimeError, match="synthetic canonical commit failure"):
            source_runtime.commit_staged_source_syncs(conn)

        assert get_source_cursor(conn, "TED") is None
        after = source_health_contract(conn, sources=["TED"])
        after_item = after["items"][0]
        assert not (
            after_item["health"] == "healthy"
            and after_item["freshness"] == "fresh"
            and after_item["stats_state"] == "current"
        ), "FETCH_SUCCESS_OUTLIVED_FAILED_INGESTION: failed canonical commit still looks fresh/current"
        assert after["summary"]["all_expected_sources_current"] is False
    finally:
        conn.close()
        source_runtime.discard_staged_source_syncs()
