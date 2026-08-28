"""Integration gate: rejected stale source truth cannot mint a fresh account decision."""
import app

from account_registry import ensure_account
from decision_log import ensure_decision_table
from source_runtime import commit_staged_source_syncs, discard_staged_source_syncs, stage_source_sync


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "stale-decision-authority:1"
ACCOUNT = "synthetic-company-stale-decision"


def _row(title, updated_at):
    return {
        "source": SOURCE,
        "external_id": EXTERNAL_ID,
        "signal_type": "TENDER",
        "title": title,
        "description": title,
        "buyer": "Synthetic Decision Authority",
        "country": "GBR",
        "cpv": "45200000",
        "value": "400000 GBP",
        "deadline": "2099-12-31",
        "publication_date": "2026-08-28",
        "published_at": "2026-08-28T00:00:00+00:00",
        "url": "https://example.test/stale-decision",
        "market": "EU",
        "source_updated_at": updated_at,
        "source_status": "active",
        "is_actionable": True,
        "lifecycle_status": "active",
        "lifecycle_reason": "publisher reports active",
    }


def _legacy_values(record, seen):
    score, label, cls, reason = app.commercial_score(
        record["title"], record["description"], record["cpv"], record["deadline"]
    )
    return (
        record["title"], record["description"], record["buyer"], record["country"],
        record["cpv"], record["value"], record["deadline"], record["publication_date"],
        record["url"], score, seen, record["published_at"], reason, label, cls,
        record["market"],
    )


def test_temporally_rejected_stale_observation_is_not_selected_for_fresh_decision(monkeypatch, tmp_path):
    db_path = tmp_path / "stale-decision.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    app.init_db()
    discard_staged_source_syncs()

    newer = _row("NEWER canonical opportunity", "2026-08-28T12:00:00+00:00")
    stale = _row("STALE late arrival", "2026-08-28T11:00:00+00:00")

    conn = app.db()
    try:
        ensure_account(conn, ACCOUNT)
        ensure_decision_table(conn)

        stage_source_sync(SOURCE, [newer], "cursor-newer")
        assert commit_staged_source_syncs(conn)["signal_records"] == 1

        prior_seen = "2026-08-28T12:01:00+00:00"
        conn.execute(
            """INSERT INTO tenders(
                title,description,buyer,country,cpv,value,deadline,publication_date,url,
                score,last_seen,published_at,match_reason,priority_label,priority_class,
                market,source,external_id,first_seen
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            _legacy_values(newer, prior_seen) + (SOURCE, EXTERNAL_ID, prior_seen),
        )
        conn.commit()

        # Mirror the already-committed legacy side of a later sync: the stale
        # observation temporarily overwrites customer projection and is tagged
        # with the latest sync-run timestamp before publisher-time authority runs.
        stale_run = "2026-08-28T13:00:00+00:00"
        values = _legacy_values(stale, stale_run)
        conn.execute(
            """UPDATE tenders SET
                title=?,description=?,buyer=?,country=?,cpv=?,value=?,deadline=?,
                publication_date=?,url=?,score=?,last_seen=?,published_at=?,match_reason=?,
                priority_label=?,priority_class=?,market=?
                WHERE source=? AND external_id=?""",
            values + (SOURCE, EXTERNAL_ID),
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
            "SELECT title,last_seen FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()
        assert restored["title"] == newer["title"]
        assert restored["last_seen"] != stale_run

        # Actual downstream selection contract: only tenders tagged with the
        # latest successful legacy sync timestamp are evaluated for accounts.
        import preload

        assert preload._record_account_decisions(conn) == 0
        count = conn.execute(
            "SELECT COUNT(*) FROM opportunity_decisions WHERE account_id=? AND source=? AND external_id=?",
            (ACCOUNT, SOURCE, EXTERNAL_ID),
        ).fetchone()[0]
        assert count == 0
    finally:
        conn.close()
        discard_staged_source_syncs()
