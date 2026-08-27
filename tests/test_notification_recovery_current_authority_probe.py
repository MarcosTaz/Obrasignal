"""Failing-before for durable Notification recovery vs current decision authority.

Test-only. No runtime repair.
"""
import sqlite3

from decision_log import record_decision
import notification_event_recovery as recovery
import notification_events
from opportunity_match_pipeline import RULE_VERSION


def _conn():
    conn = sqlite3.connect(":memory:")
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


def _tender(conn, tender_id, external_id):
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
            95,
            95,
            "2026-08-27 00:00:00",
        ),
    )


def test_recovery_must_not_reauthorize_superseded_rule_decision(monkeypatch):
    """Durable missing event work is not durable stale decision authority."""
    conn = _conn()
    assert recovery.initialize_reconciliation_baseline(
        conn, "account-a", existing_account=True
    ) == 0

    _tender(conn, 1, "stale-rule")
    record_decision(
        conn,
        "TED",
        "stale-rule",
        "QUALIFIED",
        "high score under superseded semantics",
        score=95,
        rule_version="superseded-rule",
        account_id="account-a",
    )

    _tender(conn, 2, "current-rule")
    record_decision(
        conn,
        "TED",
        "current-rule",
        "QUALIFIED",
        "control: current semantic authority",
        score=95,
        rule_version=RULE_VERSION,
        account_id="account-a",
    )
    conn.commit()

    monkeypatch.setattr(notification_events, "submit_pending_pushes", lambda *_a, **_k: 0)
    monkeypatch.setattr(notification_events, "reconcile_push_receipts", lambda *_a, **_k: 0)

    recovered = recovery.record_new_opportunities(conn, "account-a", 75)
    rows = conn.execute(
        """SELECT tender_id,event_type FROM opportunity_events
           WHERE account_id='account-a' AND event_type='new_high_match'
           ORDER BY tender_id"""
    ).fetchall()

    # Safe behavior: the superseded decision is UNKNOWN for current authority,
    # while the current-rule control remains recoverable exactly once.
    assert [row["tender_id"] for row in rows] == [2]
    assert [item["tender_id"] for item in recovered] == [2]
    conn.close()
