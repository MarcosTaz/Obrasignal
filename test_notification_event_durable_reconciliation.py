"""Passing-after invariants for durable Notification event reconciliation."""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from decision_log import record_decision
import notification_event_recovery as recovery
import notification_events


def _conn(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tenders(
            id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,
            country TEXT, url TEXT, deadline TEXT, profile_reason TEXT,
            profile_score INTEGER, score INTEGER, first_seen TEXT
        )"""
    )
    notification_events.ensure_event_table(conn)
    return conn


def _tender(conn, tender_id, external_id, *, first_seen=None):
    first_seen = first_seen or (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    conn.execute(
        """INSERT INTO tenders(
             id,source,external_id,title,country,url,deadline,
             profile_reason,profile_score,score,first_seen
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            tender_id,
            "TED",
            external_id,
            f"Obra {external_id}",
            "PT",
            f"https://example.invalid/{external_id}",
            "2099-01-01",
            "perfil: instalações",
            94,
            94,
            first_seen,
        ),
    )


def test_missing_event_survives_restart_after_legacy_window(tmp_path, monkeypatch):
    """Exact #456 boundary: durable decision cannot expire by wall clock."""
    db_path = tmp_path / "notification-restart.db"
    conn = _conn(db_path)
    _tender(conn, 1, "2026/S-restart")
    record_decision(
        conn,
        "TED",
        "2026/S-restart",
        "QUALIFIED",
        "account-specific high match",
        score=94,
        account_id="default",
    )
    conn.commit()
    conn.close()

    # No device exists, but keep the test entirely local even if future fixtures
    # add one accidentally.
    monkeypatch.setattr(notification_events, "submit_pending_pushes", lambda *_a, **_k: 0)
    monkeypatch.setattr(notification_events, "reconcile_push_receipts", lambda *_a, **_k: 0)

    conn = _conn(db_path)
    recovered = recovery.record_new_opportunities(conn, account_id="default", min_score=75)
    stored = conn.execute(
        "SELECT event_key,account_id,tender_id,event_type FROM opportunity_events WHERE tender_id=1"
    ).fetchall()
    conn.close()

    assert len(recovered) == 1
    assert len(stored) == 1
    assert stored[0]["account_id"] == "default"
    assert stored[0]["tender_id"] == 1
    assert stored[0]["event_type"] == "new_high_match"


def test_reconciliation_is_idempotent_and_does_not_require_source_replay(monkeypatch):
    conn = _conn()
    _tender(conn, 2, "2026/S-idempotent")
    record_decision(
        conn,
        "TED",
        "2026/S-idempotent",
        "QUALIFIED",
        "current high match",
        score=93,
        account_id="account-a",
    )
    monkeypatch.setattr(notification_events, "submit_pending_pushes", lambda *_a, **_k: 0)
    monkeypatch.setattr(notification_events, "reconcile_push_receipts", lambda *_a, **_k: 0)

    assert len(recovery.record_new_opportunities(conn, "account-a", 75)) == 1
    assert len(recovery.record_new_opportunities(conn, "account-a", 75)) == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM opportunity_events WHERE account_id='account-a' AND tender_id=2"
    ).fetchone()[0] == 1
    conn.close()


def test_migration_epoch_prevents_historical_notification_backfill(monkeypatch):
    conn = _conn()
    _tender(conn, 3, "2026/S-historical")
    record_decision(
        conn,
        "TED",
        "2026/S-historical",
        "QUALIFIED",
        "historical high match",
        score=95,
        account_id="default",
        decided_at="2026-08-26T22:59:59+00:00",
    )
    monkeypatch.setattr(notification_events, "submit_pending_pushes", lambda *_a, **_k: 0)
    monkeypatch.setattr(notification_events, "reconcile_push_receipts", lambda *_a, **_k: 0)

    assert recovery.record_new_opportunities(conn, "default", 75) == []
    assert conn.execute("SELECT COUNT(*) FROM opportunity_events WHERE tender_id=3").fetchone()[0] == 0
    conn.close()


def test_recovery_is_tenant_scoped(monkeypatch):
    conn = _conn()
    _tender(conn, 4, "2026/S-tenant")
    record_decision(
        conn,
        "TED",
        "2026/S-tenant",
        "QUALIFIED",
        "A high",
        score=96,
        account_id="account-a",
    )
    record_decision(
        conn,
        "TED",
        "2026/S-tenant",
        "REVIEW",
        "B below notification threshold",
        score=60,
        account_id="account-b",
    )
    monkeypatch.setattr(notification_events, "submit_pending_pushes", lambda *_a, **_k: 0)
    monkeypatch.setattr(notification_events, "reconcile_push_receipts", lambda *_a, **_k: 0)

    assert len(recovery.record_new_opportunities(conn, "account-a", 75)) == 1
    assert recovery.record_new_opportunities(conn, "account-b", 75) == []
    rows = conn.execute("SELECT account_id,tender_id FROM opportunity_events").fetchall()
    assert [tuple(row) for row in rows] == [("account-a", 4)]
    conn.close()


def test_production_installs_recovery_after_dispatch_guard_and_before_worker():
    source = (Path(__file__).resolve().parent / "cors_app.py").read_text(encoding="utf-8")
    dispatch = source.index("install_notification_dispatch_guard()")
    event_recovery = source.index("install_notification_event_recovery(_preload)")
    worker = source.index("start_background_worker()")
    assert dispatch < event_recovery < worker
