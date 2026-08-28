"""Failing-before probe: rejected stale legacy arrivals must not fabricate first_seen."""
import app

from signal_store import get_signal_record
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "stale-first-seen:1"


def _record(title, updated_at):
    return {
        "source": SOURCE,
        "external_id": EXTERNAL_ID,
        "signal_type": "TENDER",
        "title": title,
        "description": title,
        "buyer": "Synthetic Buyer",
        "country": "GBR",
        "cpv": "45200000",
        "category_code": "45200000",
        "value": "100000 GBP",
        "deadline": "2099-12-31",
        "publication_date": "2026-08-28",
        "published_at": "2026-08-28T00:00:00+00:00",
        "url": "https://example.test/stale-first-seen",
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


def test_rejected_stale_recreated_projection_uses_canonical_first_observed(monkeypatch, tmp_path):
    db_path = tmp_path / "stale-first-seen.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    app.init_db()
    discard_staged_source_syncs()

    newer = _record("NEWER canonical truth", "2026-08-28T12:00:00+00:00")
    stale = _record("STALE legacy arrival", "2026-08-28T11:00:00+00:00")

    conn = app.db()
    try:
        # Establish canonical source truth without a customer-facing legacy row.
        stage_source_sync(SOURCE, [newer], "cursor-newer")
        assert commit_staged_source_syncs(conn)["signal_records"] == 1
        assert conn.execute(
            "SELECT 1 FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone() is None

        # Model historical canonical truth whose compatibility projection is absent.
        canonical_first = "2026-08-20T09:00:00+00:00"
        canonical_last = "2026-08-20T09:05:00+00:00"
        conn.execute(
            "UPDATE signal_records SET first_observed=?,last_observed=? WHERE source=? AND signal_type='TENDER' AND external_id=?",
            (canonical_first, canonical_last, SOURCE, EXTERNAL_ID),
        )
        conn.commit()
        assert get_signal_record(conn, SOURCE, EXTERNAL_ID, "TENDER")["first_observed"] == canonical_first

        # A later legacy transaction sees only a stale publisher observation and
        # temporarily recreates the missing projection as if it were newly seen now.
        stale_run = "2026-08-28T19:00:00+00:00"
        conn.execute(
            """INSERT INTO tenders(
                title,description,buyer,country,cpv,value,deadline,publication_date,url,
                score,first_seen,last_seen,published_at,match_reason,priority_label,
                priority_class,market,source,external_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            _legacy_values(stale, stale_run, stale_run),
        )
        conn.execute(
            "INSERT INTO sync_runs(started_at,finished_at,found,new_items) VALUES(?,?,?,?)",
            (stale_run, stale_run, 1, 0),
        )
        conn.commit()

        stage_source_sync(SOURCE, [stale], "cursor-stale")
        result = commit_staged_source_syncs(conn)
        assert result["signal_records"] == 0

        restored = conn.execute(
            "SELECT title,first_seen,last_seen FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()
        assert restored["title"] == newer["title"]
        assert restored["last_seen"] == canonical_last
        assert restored["first_seen"] == canonical_first, (
            "REJECTED_STALE_FIRST_SEEN_FABRICATION: projection content was restored "
            "from canonical Signal truth but first_seen still claims the stale sync "
            "created a new opportunity"
        )
    finally:
        conn.close()
        discard_staged_source_syncs()
