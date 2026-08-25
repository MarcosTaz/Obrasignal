"""Resilience failing-before probe for fetch-health vs durable-ingestion truth.

Diagnostic composition only. Source Health, Data Reliability and Integration Lab
retain their implementation authority.
"""

import sqlite3

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
        "publication-date": "2026-08-25",
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
        # #238 correctly prevents a fetch from becoming a durable checkpoint.
        assert get_source_cursor(conn, "TED") is None

        def fail_metadata(*_args, **_kwargs):
            raise RuntimeError("synthetic canonical commit failure")

        monkeypatch.setattr(source_runtime, "persist_source_metadata", fail_metadata)
        with pytest.raises(RuntimeError, match="synthetic canonical commit failure"):
            source_runtime.commit_staged_source_syncs(conn)

        # Canonical state/cursor correctly roll back.
        assert get_source_cursor(conn, "TED") is None

        after = source_health_contract(conn, sources=["TED"])
        after_item = after["items"][0]

        # Failing-before on #359@4d6acf00: source health was independently
        # committed at fetch time and still reports fresh+healthy after the
        # canonical ingestion transaction failed. A repaired composition must
        # either expose fetch vs ingestion dimensions separately or degrade the
        # coverage/currentness used as durable-ingestion evidence.
        assert not (
            after_item["health"] == "healthy"
            and after_item["freshness"] == "fresh"
            and after_item["stats_state"] == "current"
        )
        assert after["summary"]["all_expected_sources_current"] is False
    finally:
        conn.close()
        source_runtime.discard_staged_source_syncs()
