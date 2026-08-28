"""Failing-before probe for cursor authority when legacy projection reconciliation fails."""
import sqlite3

import pytest

import app
import source_runtime
from signal_store import get_signal_record
from source_health import get_source_cursor
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "projection-failure-cursor:1"


def _record(title, updated_at):
    return {
        "source": SOURCE,
        "external_id": EXTERNAL_ID,
        "signal_type": "TENDER",
        "title": title,
        "description": "steel construction works",
        "buyer": "Synthetic Buyer",
        "country": "GBR",
        "cpv": "45200000",
        "category_code": "45200000",
        "value": "100000 GBP",
        "deadline": "2099-12-31",
        "publication_date": "2026-08-28",
        "published_at": "2026-08-28T00:00:00+00:00",
        "url": "https://example.test/projection-failure",
        "market": "EU",
        "source_updated_at": updated_at,
        "source_status": "active",
        "is_actionable": True,
        "lifecycle_status": "active",
        "lifecycle_reason": "publisher reports active",
    }


def test_projection_failure_cannot_advance_cursor_past_customer_projection(monkeypatch, tmp_path):
    db_path = tmp_path / "projection-failure.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    app.init_db()
    discard_staged_source_syncs()

    baseline = _record("baseline customer projection", "2026-08-28T10:00:00+00:00")
    newer = _record("newer canonical source truth", "2026-08-28T11:00:00+00:00")

    conn = app.db()
    try:
        stage_source_sync(SOURCE, [baseline], "cursor-baseline")
        first = commit_staged_source_syncs(conn)
        assert first["signal_records"] == 1
        assert get_source_cursor(conn, SOURCE) == "cursor-baseline"
        legacy = conn.execute(
            "SELECT title FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()
        assert legacy is not None and legacy["title"] == baseline["title"]

        def fail_projection(*_args, **_kwargs):
            raise sqlite3.OperationalError("injected legacy projection reconciliation failure")

        monkeypatch.setattr(source_runtime, "_reconcile_legacy_tender_projection", fail_projection)
        stage_source_sync(SOURCE, [newer], "cursor-must-not-advance")

        with pytest.raises(RuntimeError, match="legacy projection reconciliation failed"):
            commit_staged_source_syncs(conn)

        canonical = get_signal_record(conn, SOURCE, EXTERNAL_ID)
        assert canonical["title"] == newer["title"], (
            "probe setup requires the source-side transaction to have committed before projection failure"
        )
        legacy = conn.execute(
            "SELECT title FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()
        assert legacy["title"] == baseline["title"]

        assert get_source_cursor(conn, SOURCE) == "cursor-baseline", (
            "PROJECTION_FAILURE_CURSOR_AHEAD: source cursor advanced even though the "
            "customer-facing legacy projection failed to reconcile; the next source fetch "
            "may skip truth that customers still cannot observe"
        )
    finally:
        conn.close()
        discard_staged_source_syncs()
