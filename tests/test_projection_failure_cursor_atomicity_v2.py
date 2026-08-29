"""Corrected failing-before probe for cursor authority when projection reconciliation fails."""
import sqlite3

import pytest

import app
import source_runtime
from signal_store import get_signal_record
from source_health import get_source_cursor
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "projection-failure-cursor-v2:1"


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
        "url": "https://example.test/projection-failure-v2",
        "market": "EU",
        "source_updated_at": updated_at,
        "source_status": "active",
        "is_actionable": True,
        "lifecycle_status": "active",
        "lifecycle_reason": "publisher reports active",
    }


def _legacy_values(record, first_seen, last_seen):
    score, label, cls, reason = app.commercial_score(
        record["title"], record["description"], record["cpv"], record["deadline"]
    )
    return (
        record["title"], record["description"], record["buyer"], record["country"],
        record["cpv"], record["value"], record["deadline"], record["publication_date"],
        record["url"], score, first_seen, last_seen, record["published_at"], reason,
        label, cls, record["market"], SOURCE, EXTERNAL_ID,
    )


def test_projection_failure_cannot_advance_cursor_past_customer_projection(monkeypatch, tmp_path):
    db_path = tmp_path / "projection-failure-v2.db"
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

        # The real application writes the compatibility projection in the legacy
        # transaction before source-side commit. Build that already-consistent
        # baseline explicitly so the injected failure targets only reconciliation.
        first_seen = "2026-08-20T09:00:00+00:00"
        last_seen = "2026-08-20T09:05:00+00:00"
        conn.execute(
            """INSERT INTO tenders(
                title,description,buyer,country,cpv,value,deadline,publication_date,url,
                score,first_seen,last_seen,published_at,match_reason,priority_label,
                priority_class,market,source,external_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            _legacy_values(baseline, first_seen, last_seen),
        )
        conn.commit()

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
            "probe setup requires source-side canonical truth to commit before reconciliation fails"
        )
        legacy = conn.execute(
            "SELECT title FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()
        assert legacy["title"] == baseline["title"]

        assert get_source_cursor(conn, SOURCE) == "cursor-baseline", (
            "PROJECTION_FAILURE_CURSOR_AHEAD: source cursor advanced although the "
            "customer-facing projection did not reconcile; a subsequent fetch may skip "
            "source truth that customers still cannot observe"
        )
    finally:
        conn.close()
        discard_staged_source_syncs()
