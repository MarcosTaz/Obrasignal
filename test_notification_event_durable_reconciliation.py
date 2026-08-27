"""Passing-after invariants for durable Notification event reconciliation."""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from decision_log import record_decision
import notification_event_recovery as recovery
import notification_events
from opportunity_match_pipeline import RULE_VERSION


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


def _current_decision(conn, source, external_id, decision, reason, *, score, account_id):
    """Create the current pipeline-semantic decision assumed by these tests."""
    record_decision(
        conn,
        source,
        external_id,
        decision,
        reason,
        score=score,
        account_id=account_id,
        rule_version=RULE_VERSION,
    )


def _no_provider(monkeypatch):
    monkeypatch.setattr(notification_events, "submit_pending_pushes", lambda *_a, **_k: 0)
    monkeypatch.setattr(notification_events, "reconcile_push_receipts", lambda *_a, **_k: 0)


def test_missing_event_survives_restart_after_legacy_window(tmp_path, monkeypatch):
    """Exact #456 boundary after repaired startup: time cannot expire work."""
    db_path = tmp_path / "notification-restart.db"
    conn = _conn(db_path)

    # Repaired process startup establishes the immutable activation boundary
    # before any future account-decision work can be created.
    assert recovery.initialize_reconciliation_baseline(
        conn, "default", existing_account=True
    ) == 0

    _tender(conn, 1, "2026/S-restart")
    _current_decision(
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

    _no_provider(monkeypatch)
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
    recovery.initialize_reconciliation_baseline(conn, "account-a", existing_account=True)
    _tender(conn, 2, "2026/S-idempotent")
    _current_decision(
        conn,
        "TED",
        "2026/S-idempotent",
        "QUALIFIED",
        "current high match",
        score=93,
        account_id="account-a",
    )
    _no_provider(monkeypatch)

    assert len(recovery.record_new_opportunities(conn, "account-a", 75)) == 1
    assert len(recovery.record_new_opportunities(conn, "account-a", 75)) == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM opportunity_events WHERE account_id='account-a' AND tender_id=2"
    ).fetchone()[0] == 1
    conn.close()


def test_existing_account_baseline_blocks_historical_notification_backfill(monkeypatch):
    conn = _conn()
    _tender(conn, 3, "2026/S-historical")
    _current_decision(
        conn,
        "TED",
        "2026/S-historical",
        "QUALIFIED",
        "historical high match",
        score=95,
        account_id="default",
    )
    baseline = recovery.initialize_reconciliation_baseline(
        conn, "default", existing_account=True
    )
    assert baseline > 0
    _no_provider(monkeypatch)

    assert recovery.record_new_opportunities(conn, "default", 75) == []
    assert conn.execute(
        "SELECT COUNT(*) FROM opportunity_events WHERE tender_id=3 AND event_type='new_high_match'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM opportunity_events WHERE account_id='default' AND event_type=?",
        (recovery.BASELINE_EVENT_TYPE,),
    ).fetchone()[0] == 1
    conn.close()


def test_baseline_is_immutable_across_restart(tmp_path):
    db_path = tmp_path / "baseline.sqlite"
    conn = _conn(db_path)
    _tender(conn, 10, "2026/S-old")
    _current_decision(conn, "TED", "2026/S-old", "QUALIFIED", "old", score=95, account_id="account-a")
    first = recovery.initialize_reconciliation_baseline(conn, "account-a", existing_account=True)
    conn.close()

    conn = _conn(db_path)
    _tender(conn, 11, "2026/S-new")
    _current_decision(conn, "TED", "2026/S-new", "QUALIFIED", "new", score=96, account_id="account-a")
    second = recovery.initialize_reconciliation_baseline(conn, "account-a", existing_account=True)
    assert second == first
    assert recovery.reconciliation_baseline_id(conn, "account-a") == first
    conn.close()


def test_new_account_without_startup_baseline_starts_from_zero(monkeypatch):
    conn = _conn()
    _tender(conn, 12, "2026/S-new-account")
    _current_decision(
        conn,
        "TED",
        "2026/S-new-account",
        "QUALIFIED",
        "first account decision",
        score=91,
        account_id="new-account",
    )
    _no_provider(monkeypatch)

    recovered = recovery.record_new_opportunities(conn, "new-account", 75)
    assert len(recovered) == 1
    assert recovery.reconciliation_baseline_id(conn, "new-account") == 0
    conn.close()


def test_recovery_is_tenant_scoped(monkeypatch):
    conn = _conn()
    recovery.initialize_existing_account_baselines(conn, ["account-a", "account-b"])
    _tender(conn, 4, "2026/S-tenant")
    _current_decision(
        conn,
        "TED",
        "2026/S-tenant",
        "QUALIFIED",
        "A high",
        score=96,
        account_id="account-a",
    )
    _current_decision(
        conn,
        "TED",
        "2026/S-tenant",
        "REVIEW",
        "B below notification threshold",
        score=60,
        account_id="account-b",
    )
    _no_provider(monkeypatch)

    assert len(recovery.record_new_opportunities(conn, "account-a", 75)) == 1
    assert recovery.record_new_opportunities(conn, "account-b", 75) == []
    rows = conn.execute(
        "SELECT account_id,tender_id FROM opportunity_events WHERE event_type='new_high_match'"
    ).fetchall()
    assert [tuple(row) for row in rows] == [("account-a", 4)]
    conn.close()


def test_production_baselines_existing_accounts_before_worker_and_installs_recovery():
    source = (Path(__file__).resolve().parent / "cors_app.py").read_text(encoding="utf-8")
    baseline = source.index("initialize_existing_account_baselines(")
    dispatch = source.index("install_notification_dispatch_guard()")
    event_recovery = source.index("install_notification_event_recovery(_preload)")
    worker = source.index("start_background_worker()")
    assert baseline < dispatch < event_recovery < worker
