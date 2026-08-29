"""Probe multi-source cursor + health compensation after projection failure."""
import sqlite3

import pytest

import app
import source_runtime
from source_health import get_source_cursor, record_source_result, source_health_contract
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCES = ("TED", "BASE")
IDS = {"TED": "projection-multi-ted:1", "BASE": "projection-multi-base:1"}


def _record(source, updated_at):
    return {
        "source": source,
        "external_id": IDS[source],
        "signal_type": "TENDER",
        "title": f"{source} synthetic opportunity",
        "description": "construction works",
        "country": "PRT",
        "cpv": "45200000",
        "category_code": "45200000",
        "source_updated_at": updated_at,
        "source_status": "active",
        "is_actionable": True,
        "lifecycle_status": "active",
        "lifecycle_reason": "publisher reports active",
    }


def _health(conn, source):
    return source_health_contract(conn, sources=[source])["items"][0]


def test_projection_failure_restores_all_cursors_and_continues_health_compensation(monkeypatch, tmp_path):
    db_path = tmp_path / "projection-multisource.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    app.init_db()
    discard_staged_source_syncs()

    conn = app.db()
    try:
        for source in SOURCES:
            stage_source_sync(source, [_record(source, "2026-08-28T10:00:00+00:00")], f"{source}-cursor-baseline")
        first = commit_staged_source_syncs(conn)
        assert first["sources"] == 2
        for source in SOURCES:
            record_source_result(conn, source, success=True, duration_ms=5, found=1, new_items=1)
            assert _health(conn, source)["health"] == "healthy"

        def fail_projection(*_args, **_kwargs):
            raise sqlite3.OperationalError("injected multi-source projection failure")

        real_health = source_runtime.record_source_projection_failure
        attempted = []

        def fail_first_health(conn_, source, *, error):
            attempted.append(source)
            if source == "TED":
                raise sqlite3.OperationalError("injected TED projection-health failure")
            return real_health(conn_, source, error=error)

        monkeypatch.setattr(source_runtime, "_reconcile_legacy_tender_projection", fail_projection)
        monkeypatch.setattr(source_runtime, "record_source_projection_failure", fail_first_health)

        for source in SOURCES:
            stage_source_sync(source, [_record(source, "2026-08-28T11:00:00+00:00")], f"{source}-cursor-must-restore")

        with pytest.raises(RuntimeError, match="source projection-health compensation failed for TED") as raised:
            commit_staged_source_syncs(conn)

        assert raised.value.__cause__ is not None
        assert isinstance(raised.value.__cause__, sqlite3.OperationalError)
        assert attempted == ["TED", "BASE"]

        for source in SOURCES:
            assert get_source_cursor(conn, source) == f"{source}-cursor-baseline"

        assert _health(conn, "TED")["health"] == "healthy", "failed TED health write must not fabricate degradation"
        assert _health(conn, "BASE")["health"] == "degraded"
        assert _health(conn, "BASE")["last_error"].startswith("projection_reconciliation_failed:OperationalError")
    finally:
        conn.close()
        discard_staged_source_syncs()
