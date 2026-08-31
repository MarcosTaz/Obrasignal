"""Failing-before integration probe for source truth -> legacy customer projection.

The source-side transaction already rejects stale publisher observations. The
legacy ``tenders`` projection consumed by Radar/decisioning must not diverge and
accept the same rejected observation merely because it arrived later.
"""
from datetime import datetime, timezone

import app
from signal_store import get_signal_record
from source_metadata import get_source_metadata
from source_runtime import (
    commit_staged_source_syncs,
    discard_staged_source_syncs,
    stage_source_sync,
)


SOURCE = "UK_PROCUREMENT"
EXTERNAL_ID = "temporal-split-brain:1"


def _row(*, title, updated_at):
    return {
        "source": SOURCE,
        "external_id": EXTERNAL_ID,
        "signal_type": "TENDER",
        "title": title,
        "description": title,
        "buyer": "Synthetic Authority",
        "country": "GBR",
        "cpv": "45200000",
        "value": "250000 GBP",
        "deadline": "2099-12-31",
        "publication_date": "2026-08-28",
        "published_at": "2026-08-28T00:00:00+00:00",
        "url": "https://example.test/opportunity",
        "market": "EU",
        "source_updated_at": updated_at,
        "source_status": "active",
        "is_actionable": True,
        "lifecycle_status": "active",
        "lifecycle_reason": "publisher reports active",
    }


def test_temporal_rejection_also_protects_legacy_tender_projection(monkeypatch, tmp_path):
    db_path = tmp_path / "temporal-projection.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    app.init_db()
    discard_staged_source_syncs()

    newer = _row(
        title="NEWER authoritative publisher state",
        updated_at="2026-08-28T12:00:00+00:00",
    )
    stale = _row(
        title="STALE late arrival must never become customer truth",
        updated_at="2026-08-28T11:00:00+00:00",
    )

    conn = app.db()
    try:
        stage_source_sync(SOURCE, [newer], "cursor-authoritative")
        first = commit_staged_source_syncs(conn)
        assert first["signal_records"] == 1

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO tenders(
                source,external_id,title,description,buyer,country,cpv,value,deadline,
                publication_date,url,score,first_seen,last_seen,published_at,market
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                SOURCE,
                EXTERNAL_ID,
                newer["title"],
                newer["description"],
                newer["buyer"],
                newer["country"],
                newer["cpv"],
                newer["value"],
                newer["deadline"],
                newer["publication_date"],
                newer["url"],
                10,
                now,
                now,
                newer["published_at"],
                newer["market"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    def fetch_stale_normalized_row():
        # This mirrors staged connectors in preload: the same normalized record
        # enters the legacy sync path while source_runtime retains publisher-time
        # authority for the durable source-side transaction.
        stage_source_sync(SOURCE, [stale], "cursor-stale-fetch")
        return [dict(stale)]

    monkeypatch.setattr(app, "fetch_ted", lambda: [])
    monkeypatch.setattr(app, "fetch_base", fetch_stale_normalized_row)

    # Runtime ordering today is legacy transaction first, then source-side commit.
    app.sync_once()

    conn = app.db()
    try:
        second = commit_staged_source_syncs(conn)
        assert second["signal_records"] == 0
        assert second["metadata_records"] == 0
        assert second["lifecycle_records"] == 0

        signal = get_signal_record(conn, SOURCE, EXTERNAL_ID)
        metadata = get_source_metadata(conn, SOURCE, EXTERNAL_ID)
        tender = conn.execute(
            "SELECT title FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, EXTERNAL_ID),
        ).fetchone()

        # Source authority correctly rejects the stale observation.
        assert signal["title"] == newer["title"]
        assert metadata["source_updated_at"] == newer["source_updated_at"]

        # Customer-facing legacy truth must be protected by the same authority.
        # Current code fails here: app.sync_once overwrites the tender before the
        # source-side temporal gate rejects the stale staged observation.
        assert tender["title"] == newer["title"]
    finally:
        conn.close()
        discard_staged_source_syncs()
