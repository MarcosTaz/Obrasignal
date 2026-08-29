"""Failing-before: customer projection failure must degrade public Source Health truth."""
import sqlite3

import pytest

import app
import source_runtime
from source_health import record_source_result, source_health_contract
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "projection-failure-health:1"


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
        "url": "https://example.test/projection-health",
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


def _health(conn):
    return source_health_contract(conn, sources=[SOURCE])["items"][0]


def test_projection_failure_degrades_source_health_even_when_source_transaction_committed(monkeypatch, tmp_path):
    db_path = tmp_path / "projection-health.db"
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

        conn.execute(
            """INSERT INTO tenders(
                title,description,buyer,country,cpv,value,deadline,publication_date,url,
                score,first_seen,last_seen,published_at,match_reason,priority_label,
                priority_class,market,source,external_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            _legacy_values(
                baseline,
                "2026-08-20T09:00:00+00:00",
                "2026-08-20T09:05:00+00:00",
            ),
        )
        conn.commit()

        record_source_result(
            conn,
            SOURCE,
            success=True,
            duration_ms=5,
            found=1,
            new_items=1,
        )
        before = _health(conn)
        assert before["health"] == "healthy"

        def fail_projection(*_args, **_kwargs):
            raise sqlite3.OperationalError("injected legacy projection reconciliation failure")

        monkeypatch.setattr(source_runtime, "_reconcile_legacy_tender_projection", fail_projection)
        stage_source_sync(SOURCE, [newer], "cursor-must-restore")

        with pytest.raises(RuntimeError, match="legacy projection reconciliation failed"):
            commit_staged_source_syncs(conn)

        after = _health(conn)
        assert after["last_success"] == before["last_success"]
        assert after["health"] == "degraded", (
            "PROJECTION_FAILURE_FALSE_HEALTH: source-side persistence committed but the "
            "customer-facing projection failed; Source Health must not remain healthy/current"
        )
        assert after["consecutive_failures"] == 1
        assert after["last_failed"] is not None
    finally:
        conn.close()
        discard_staged_source_syncs()
