"""Customer read-model proof: rejected stale input cannot become 'new in 24h'."""
import app

from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "stale-new24:1"


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
        "url": "https://example.test/stale-new24",
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


def test_rejected_stale_recreation_is_not_counted_as_new_24h(monkeypatch, tmp_path):
    db_path = tmp_path / "stale-new24.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    app.init_db()
    discard_staged_source_syncs()

    newer = _record("NEWER canonical opportunity", "2026-08-28T12:00:00+00:00")
    stale = _record("STALE late arrival", "2026-08-28T11:00:00+00:00")

    conn = app.db()
    try:
        stage_source_sync(SOURCE, [newer], "cursor-newer")
        assert commit_staged_source_syncs(conn)["signal_records"] == 1

        canonical_first = "2000-01-01T09:00:00+00:00"
        canonical_last = "2026-08-20T09:05:00+00:00"
        conn.execute(
            "UPDATE signal_records SET first_observed=?,last_observed=? WHERE source=? AND signal_type='TENDER' AND external_id=?",
            (canonical_first, canonical_last, SOURCE, EXTERNAL_ID),
        )
        conn.commit()

        stale_run = "2099-01-01T19:00:00+00:00"
        conn.execute(
            """INSERT INTO tenders(
                title,description,buyer,country,cpv,value,deadline,publication_date,url,
                score,first_seen,last_seen,published_at,match_reason,priority_label,
                priority_class,market,source,external_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            _legacy_values(stale, stale_run, stale_run),
        )
        conn.commit()

        stage_source_sync(SOURCE, [stale], "cursor-stale")
        result = commit_staged_source_syncs(conn)
        assert result["signal_records"] == 0

        projection = conn.execute(
            "SELECT title,first_seen,last_seen FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()
        assert projection["title"] == newer["title"]
        assert projection["first_seen"] == canonical_first
        assert projection["last_seen"] == canonical_last
    finally:
        conn.close()
        discard_staged_source_syncs()

    stats = app.stats_for("EU")
    assert stats["new24"] == 0, (
        "REJECTED_STALE_NEW24_FABRICATION: a temporally rejected observation made an "
        "old canonical opportunity appear in the customer-facing 'new in 24h' statistic"
    )
