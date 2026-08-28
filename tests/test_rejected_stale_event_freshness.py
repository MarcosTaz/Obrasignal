"""Downstream proof: rejected stale recreation cannot manufacture a new-opportunity event."""
import app

from account_registry import ensure_account
from decision_log import ensure_decision_table, record_decision
from notification_events import record_new_opportunities
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "stale-event-freshness:1"
ACCOUNT = "synthetic-stale-event-account"


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
        "url": "https://example.test/stale-event",
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


def test_rejected_stale_recreation_cannot_emit_new_high_match_event(monkeypatch, tmp_path):
    db_path = tmp_path / "stale-event.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    app.init_db()
    discard_staged_source_syncs()

    newer = _record("NEWER canonical opportunity", "2026-08-28T12:00:00+00:00")
    stale = _record("STALE late arrival", "2026-08-28T11:00:00+00:00")

    conn = app.db()
    try:
        ensure_account(conn, ACCOUNT)
        ensure_decision_table(conn)

        stage_source_sync(SOURCE, [newer], "cursor-newer")
        assert commit_staged_source_syncs(conn)["signal_records"] == 1

        canonical_first = "2026-08-20T09:00:00+00:00"
        canonical_last = "2026-08-20T09:05:00+00:00"
        conn.execute(
            "UPDATE signal_records SET first_observed=?,last_observed=? WHERE source=? AND signal_type='TENDER' AND external_id=?",
            (canonical_first, canonical_last, SOURCE, EXTERNAL_ID),
        )
        conn.commit()

        stale_run = "2026-08-28T19:00:00+00:00"
        conn.execute(
            """INSERT INTO tenders(
                title,description,buyer,country,cpv,value,deadline,publication_date,url,
                score,first_seen,last_seen,published_at,match_reason,priority_label,
                priority_class,market,source,external_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            _legacy_values(stale, stale_run, stale_run),
        )
        tender_id = conn.execute(
            "SELECT id FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()[0]
        conn.commit()

        # Existing account decision is deliberately high. The only reason a new
        # event could appear now would be fabricated compatibility freshness.
        record_decision(
            conn,
            ACCOUNT,
            SOURCE,
            EXTERNAL_ID,
            "QUALIFIED",
            95,
            {"profile_score": 95},
            "synthetic high match",
        )

        stage_source_sync(SOURCE, [stale], "cursor-stale")
        result = commit_staged_source_syncs(conn)
        assert result["signal_records"] == 0

        projection = conn.execute(
            "SELECT id,title,first_seen,last_seen FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()
        assert projection["id"] == tender_id
        assert projection["title"] == newer["title"]
        assert projection["first_seen"] == canonical_first
        assert projection["last_seen"] == canonical_last

        events = record_new_opportunities(conn, account_id=ACCOUNT, min_score=75)
        assert events == [], (
            "REJECTED_STALE_EVENT_FRESHNESS: temporally rejected source input caused "
            "an old canonical opportunity to be emitted as a new high-match event"
        )
        count = conn.execute(
            "SELECT COUNT(*) FROM opportunity_events WHERE account_id=? AND tender_id=?",
            (ACCOUNT, tender_id),
        ).fetchone()[0]
        assert count == 0
    finally:
        conn.close()
        discard_staged_source_syncs()
