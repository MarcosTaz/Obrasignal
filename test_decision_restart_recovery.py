"""Passing-after invariants for durable account-decision rediscovery."""

import sqlite3

from decision_log import ensure_decision_table, record_decision
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


def test_restart_rediscovery_does_not_depend_on_source_replay(monkeypatch):
    conn = _conn()
    calls = _capture(monkeypatch)
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

    assert recorded == 1
    assert calls == [("tenant-a", "TED", "restart-missing-decision")]


def test_missing_decision_rediscovery_is_account_complete(monkeypatch):
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


def test_old_row_with_existing_account_decision_is_not_reprocessed_without_replay(monkeypatch):
    conn = _conn()
    calls = _capture(monkeypatch)
    conn.execute(
        "INSERT INTO tenders(source,external_id,deadline,last_seen) VALUES(?,?,?,?)",
        ("TED", "already-decided", "2099-12-31", "2026-08-25T20:00:00+00:00"),
    )
    conn.execute(
        "INSERT INTO sync_runs(started_at,finished_at) VALUES(?,?)",
        ("2026-08-25T20:05:00+00:00", "2026-08-25T20:06:00+00:00"),
    )
    ensure_decision_table(conn)
    record_decision(
        conn,
        "TED",
        "already-decided",
        "REVIEW",
        "existing durable decision",
        account_id="tenant-a",
    )

    recorded = read_model.record_account_decisions(
        conn, list_active_accounts=lambda _conn: ["tenant-a"]
    )

    assert recorded == 0
    assert calls == []


def test_source_replay_still_reclassifies_existing_decision(monkeypatch):
    conn = _conn()
    calls = _capture(monkeypatch)
    latest = "2026-08-25T20:06:00+00:00"
    conn.execute(
        "INSERT INTO tenders(source,external_id,deadline,last_seen) VALUES(?,?,?,?)",
        ("TED", "replayed-existing", "2099-12-31", latest),
    )
    conn.execute(
        "INSERT INTO sync_runs(started_at,finished_at) VALUES(?,?)",
        ("2026-08-25T20:05:00+00:00", latest),
    )
    ensure_decision_table(conn)
    record_decision(
        conn,
        "TED",
        "replayed-existing",
        "REVIEW",
        "older decision",
        account_id="tenant-a",
    )

    recorded = read_model.record_account_decisions(
        conn, list_active_accounts=lambda _conn: ["tenant-a"]
    )

    assert recorded == 1
    assert calls == [("tenant-a", "TED", "replayed-existing")]


def test_missing_decision_can_reconcile_even_without_completed_sync(monkeypatch):
    conn = _conn()
    calls = _capture(monkeypatch)
    conn.execute(
        "INSERT INTO tenders(source,external_id,deadline,last_seen) VALUES(?,?,?,?)",
        ("TED", "missing-without-run", "2099-12-31", "2026-08-25T20:00:00+00:00"),
    )
    conn.commit()

    recorded = read_model.record_account_decisions(
        conn, list_active_accounts=lambda _conn: ["tenant-a"]
    )

    assert recorded == 1
    assert calls == [("tenant-a", "TED", "missing-without-run")]
