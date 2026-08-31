"""Failure-injection gates for canonical source truth -> legacy projection recovery."""
from datetime import datetime, timezone
import sqlite3

import pytest

import app
import source_runtime
from signal_store import get_signal_record
from source_runtime import (
    commit_staged_source_syncs,
    discard_staged_source_syncs,
    stage_source_sync,
)


SOURCE = "UK_PROCUREMENT"


def _row(external_id, *, title, updated_at):
    return {
        "source": SOURCE,
        "external_id": external_id,
        "signal_type": "TENDER",
        "title": title,
        "description": title,
        "buyer": "Synthetic Failure Authority",
        "country": "GBR",
        "cpv": "45200000",
        "value": "300000 GBP",
        "deadline": "2099-12-31",
        "publication_date": "2026-08-28",
        "published_at": "2026-08-28T00:00:00+00:00",
        "url": "https://example.test/failure",
        "market": "EU",
        "source_updated_at": updated_at,
        "source_status": "active",
        "is_actionable": True,
        "lifecycle_status": "active",
        "lifecycle_reason": "publisher reports active",
    }


def _insert_legacy(conn, record, *, last_seen):
    score, label, cls, reason = app.commercial_score(
        record["title"], record["description"], record["cpv"], record["deadline"]
    )
    conn.execute(
        """INSERT INTO tenders(
            source,external_id,title,description,buyer,country,cpv,value,deadline,
            publication_date,url,score,first_seen,last_seen,published_at,
            match_reason,priority_label,priority_class,market
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            record["source"],
            record["external_id"],
            record["title"],
            record["description"],
            record["buyer"],
            record["country"],
            record["cpv"],
            record["value"],
            record["deadline"],
            record["publication_date"],
            record["url"],
            score,
            last_seen,
            last_seen,
            record["published_at"],
            reason,
            label,
            cls,
            record["market"],
        ),
    )


def _overwrite_legacy(conn, record, *, last_seen):
    conn.execute(
        """UPDATE tenders SET title=?,description=?,buyer=?,country=?,cpv=?,value=?,
           deadline=?,publication_date=?,url=?,last_seen=?,published_at=?,market=?
           WHERE source=? AND external_id=?""",
        (
            record["title"],
            record["description"],
            record["buyer"],
            record["country"],
            record["cpv"],
            record["value"],
            record["deadline"],
            record["publication_date"],
            record["url"],
            last_seen,
            record["published_at"],
            record["market"],
            record["source"],
            record["external_id"],
        ),
    )


def _latest_sync(conn, finished_at):
    conn.execute(
        "INSERT INTO sync_runs(started_at,finished_at,found,new_items) VALUES(?,?,?,?)",
        (finished_at, finished_at, 1, 0),
    )
    conn.commit()


def _inject_metadata_failure(monkeypatch):
    def fail_metadata(_conn, _records, *, observed_at=None, commit=True):
        raise sqlite3.OperationalError("injected source metadata failure")

    monkeypatch.setattr(source_runtime, "persist_source_metadata", fail_metadata)


def test_source_transaction_failure_restores_prior_canonical_legacy_projection(monkeypatch, tmp_path):
    db_path = tmp_path / "projection-existing.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    app.init_db()
    discard_staged_source_syncs()

    external_id = "projection-failure:existing"
    prior = _row(
        external_id,
        title="PRIOR canonical publisher truth",
        updated_at="2026-08-28T10:00:00+00:00",
    )
    incoming = _row(
        external_id,
        title="INCOMING legacy write whose source transaction fails",
        updated_at="2026-08-28T11:00:00+00:00",
    )

    conn = app.db()
    try:
        stage_source_sync(SOURCE, [prior], "cursor-prior")
        assert commit_staged_source_syncs(conn)["signal_records"] == 1

        initial_seen = "2026-08-28T10:01:00+00:00"
        _insert_legacy(conn, prior, last_seen=initial_seen)
        conn.commit()

        failed_run_seen = "2026-08-28T11:01:00+00:00"
        _overwrite_legacy(conn, incoming, last_seen=failed_run_seen)
        _latest_sync(conn, failed_run_seen)
        stage_source_sync(SOURCE, [incoming], "cursor-must-rollback")
        _inject_metadata_failure(monkeypatch)

        with pytest.raises(sqlite3.OperationalError, match="injected source metadata failure"):
            commit_staged_source_syncs(conn)

        signal = get_signal_record(conn, SOURCE, external_id)
        tender = conn.execute(
            "SELECT title,last_seen FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, external_id),
        ).fetchone()

        assert signal["title"] == prior["title"]
        assert signal["source_updated_at"] == prior["source_updated_at"]
        assert tender["title"] == prior["title"]
        assert tender["last_seen"] == signal["last_observed"]
        assert tender["last_seen"] != failed_run_seen
        assert commit_staged_source_syncs(conn) == {
            "sources": 0,
            "signal_records": 0,
            "metadata_records": 0,
            "lifecycle_records": 0,
            "cursors": 0,
        }
    finally:
        conn.close()
        discard_staged_source_syncs()


def test_first_time_source_transaction_failure_removes_legacy_orphan(monkeypatch, tmp_path):
    db_path = tmp_path / "projection-first-time.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    app.init_db()
    discard_staged_source_syncs()

    record = _row(
        "projection-failure:first-time",
        title="FIRST-TIME legacy row must not survive source rollback",
        updated_at="2026-08-28T12:00:00+00:00",
    )
    failed_run_seen = datetime.now(timezone.utc).isoformat()

    conn = app.db()
    try:
        _insert_legacy(conn, record, last_seen=failed_run_seen)
        _latest_sync(conn, failed_run_seen)
        stage_source_sync(SOURCE, [record], "cursor-first-time-must-rollback")
        _inject_metadata_failure(monkeypatch)

        with pytest.raises(sqlite3.OperationalError, match="injected source metadata failure"):
            commit_staged_source_syncs(conn)

        assert get_signal_record(conn, SOURCE, record["external_id"]) is None
        assert conn.execute(
            "SELECT 1 FROM tenders WHERE source=? AND external_id=?",
            (SOURCE, record["external_id"]),
        ).fetchone() is None
        assert commit_staged_source_syncs(conn) == {
            "sources": 0,
            "signal_records": 0,
            "metadata_records": 0,
            "lifecycle_records": 0,
            "cursors": 0,
        }
    finally:
        conn.close()
        discard_staged_source_syncs()
