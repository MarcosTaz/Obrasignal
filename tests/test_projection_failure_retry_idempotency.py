"""Retry probe after a post-commit customer projection failure.

Canonical source truth may already have committed while the customer-facing legacy
projection failed and the source cursor was restored. Retrying the same publisher
observation must converge the projection and cursor without manufacturing another
canonical observation merely because the retry arrived later.
"""
import sqlite3

import pytest

import app
import source_runtime
from signal_store import get_signal_record
from source_health import get_source_cursor
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "projection-retry-idempotency:1"


def _record(title, updated_at):
    return {
        "source": SOURCE,
        "external_id": EXTERNAL_ID,
        "signal_type": "TENDER",
        "title": title,
        "description": "synthetic projection retry evidence",
        "buyer": "Synthetic Buyer",
        "country": "GBR",
        "cpv": "45200000",
        "category_code": "45200000",
        "value": "100000 GBP",
        "deadline": "2099-12-31",
        "publication_date": "2026-08-28",
        "published_at": "2026-08-28T00:00:00+00:00",
        "url": "https://example.test/projection-retry",
        "market": "EU",
        "source_updated_at": updated_at,
        "source_status": "active",
        "is_actionable": True,
        "lifecycle_status": "active",
        "lifecycle_reason": "publisher reports active",
    }


def _insert_legacy(conn, record):
    score, label, cls, reason = app.commercial_score(
        record["title"], record["description"], record["cpv"], record["deadline"]
    )
    conn.execute(
        """INSERT INTO tenders(
            title,description,buyer,country,cpv,value,deadline,publication_date,url,
            score,first_seen,last_seen,published_at,match_reason,priority_label,
            priority_class,market,source,external_id
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            record["title"], record["description"], record["buyer"], record["country"],
            record["cpv"], record["value"], record["deadline"], record["publication_date"],
            record["url"], score, "2026-08-20T09:00:00+00:00", "2026-08-20T09:05:00+00:00",
            record["published_at"], reason, label, cls, record["market"], SOURCE, EXTERNAL_ID,
        ),
    )
    conn.commit()


def test_retry_after_projection_failure_converges_without_duplicate_canonical_write(monkeypatch, tmp_path):
    db_path = tmp_path / "projection-retry.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    app.init_db()
    discard_staged_source_syncs()

    baseline = _record("baseline customer projection", "2026-08-28T10:00:00+00:00")
    newer = _record("newer canonical source truth", "2026-08-28T11:00:00+00:00")

    conn = app.db()
    try:
        stage_source_sync(SOURCE, [baseline], "cursor-baseline")
        assert commit_staged_source_syncs(conn)["signal_records"] == 1
        _insert_legacy(conn, baseline)

        real_reconcile = source_runtime._reconcile_legacy_tender_projection

        def fail_projection(*_args, **_kwargs):
            raise sqlite3.OperationalError("injected projection failure before retry")

        monkeypatch.setattr(source_runtime, "_reconcile_legacy_tender_projection", fail_projection)
        stage_source_sync(SOURCE, [newer], "cursor-newer")
        with pytest.raises(RuntimeError, match="legacy projection reconciliation failed"):
            commit_staged_source_syncs(conn)

        # Source-side canonical truth committed, but retryability compensation kept
        # cursor and customer projection at the prior successfully represented state.
        assert get_signal_record(conn, SOURCE, EXTERNAL_ID)["title"] == newer["title"]
        assert get_source_cursor(conn, SOURCE) == "cursor-baseline"
        assert conn.execute(
            "SELECT title FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()["title"] == baseline["title"]

        monkeypatch.setattr(source_runtime, "_reconcile_legacy_tender_projection", real_reconcile)
        stage_source_sync(SOURCE, [newer], "cursor-newer")
        retried = commit_staged_source_syncs(conn)

        # Equal publisher time is not a second canonical observation. The retry is
        # nevertheless allowed to converge the customer projection and checkpoint.
        assert retried["signal_records"] == 0
        assert get_source_cursor(conn, SOURCE) == "cursor-newer"
        canonical = get_signal_record(conn, SOURCE, EXTERNAL_ID)
        projected = conn.execute(
            "SELECT title,first_seen FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()
        assert canonical["title"] == newer["title"]
        assert projected["title"] == canonical["title"], (
            "PROJECTION_RETRY_DID_NOT_CONVERGE: equal-time retry was correctly rejected "
            "as a new canonical write but failed to repair the customer projection"
        )
        assert projected["first_seen"] == canonical["first_observed"]
        assert conn.execute(
            "SELECT COUNT(*) FROM signal_records WHERE source=? AND signal_type='TENDER' AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()[0] == 1
    finally:
        conn.close()
        discard_staged_source_syncs()
