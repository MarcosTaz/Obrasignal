"""Execution Factory failing-before: durable opportunities must not lose required decisions.

DO NOT MERGE / NOT OWNER REPAIR / NOT CANONICAL.

This probe isolates the restart boundary after an opportunity is durable but before
its account decision is recorded.  It intentionally exercises the current
latest-sync-only selector without changing decision business semantics.
"""
import sqlite3

import lifecycle_read_model as read_model


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            deadline TEXT,
            last_seen TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE sync_runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            found INTEGER DEFAULT 0,
            new_items INTEGER DEFAULT 0
        )"""
    )
    return conn


def _capture(monkeypatch):
    calls = []

    def fake_persist_and_classify(conn, row, is_new, account_id="default"):
        calls.append((account_id, row["source"], row["external_id"]))
        return None

    monkeypatch.setattr(read_model, "persist_and_classify", fake_persist_and_classify)
    return calls


def test_restart_rediscovery_does_not_depend_on_source_replaying_opportunity(monkeypatch):
    """A durable missing decision must survive a later sync that omits the row."""
    conn = _conn()
    calls = _capture(monkeypatch)

    # Cycle 1 durably persisted the opportunity, then the process died before
    # decision creation.  Cycle 2 is the post-restart run and the incremental
    # source does not return this already-known opportunity again.
    conn.execute(
        "INSERT INTO tenders(source,external_id,deadline,last_seen) VALUES(?,?,?,?)",
        ("TED", "restart-missing-decision", "2099-12-31", "2026-08-25T20:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO sync_runs(started_at,finished_at) VALUES(?,?)",
        ("2026-08-25T20:05:00+00:00", "2026-08-25T20:06:00+00:00"),
    )
    conn.commit()

    recorded = read_model.record_account_decisions(
        conn, list_active_accounts=lambda _conn: ["tenant-a"]
    )

    # Required invariant: durable eligible opportunity + missing decision stays
    # discoverable independently of whether the source happens to replay it.
    assert recorded == 1
    assert calls == [("tenant-a", "TED", "restart-missing-decision")]


def test_current_selector_recovers_only_when_source_replays_row(monkeypatch):
    """Control: source replay moves last_seen into the latest run and is selected."""
    conn = _conn()
    calls = _capture(monkeypatch)
    latest = "2026-08-25T20:06:00+00:00"
    conn.execute(
        "INSERT INTO tenders(source,external_id,deadline,last_seen) VALUES(?,?,?,?)",
        ("TED", "replayed-decision", "2099-12-31", latest),
    )
    conn.execute(
        "INSERT INTO sync_runs(started_at,finished_at) VALUES(?,?)",
        ("2026-08-25T20:05:00+00:00", latest),
    )
    conn.commit()

    recorded = read_model.record_account_decisions(
        conn, list_active_accounts=lambda _conn: ["tenant-a"]
    )

    assert recorded == 1
    assert calls == [("tenant-a", "TED", "replayed-decision")]


def test_missing_decision_rediscovery_is_account_complete(monkeypatch):
    """Missing work must remain rediscoverable for every applicable tenant."""
    conn = _conn()
    calls = _capture(monkeypatch)
    conn.execute(
        "INSERT INTO tenders(source,external_id,deadline,last_seen) VALUES(?,?,?,?)",
        ("TED", "multi-account-missing", "2099-12-31", "2026-08-25T20:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO sync_runs(started_at,finished_at) VALUES(?,?)",
        ("2026-08-25T20:05:00+00:00", "2026-08-25T20:06:00+00:00"),
    )
    conn.commit()

    recorded = read_model.record_account_decisions(
        conn, list_active_accounts=lambda _conn: ["tenant-a", "tenant-b"]
    )

    assert recorded == 2
    assert calls == [
        ("tenant-a", "TED", "multi-account-missing"),
        ("tenant-b", "TED", "multi-account-missing"),
    ]
