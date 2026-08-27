"""Regression coverage for durable Notification recovery vs current decision authority."""
import json
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


def _disable_provider(monkeypatch):
    monkeypatch.setattr(notification_events, "submit_pending_pushes", lambda *_a, **_k: 0)
    monkeypatch.setattr(notification_events, "reconcile_push_receipts", lambda *_a, **_k: 0)


def _event_tender_ids(conn, account_id="account-a"):
    return [
        row["tender_id"]
        for row in conn.execute(
            """SELECT tender_id FROM opportunity_events
               WHERE account_id=? AND event_type='new_high_match'
               ORDER BY tender_id""",
            (account_id,),
        ).fetchall()
    ]


def test_recovery_must_not_reauthorize_superseded_rule_decision(monkeypatch):
    """Durable missing event work is not durable stale rule authority."""
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
    _disable_provider(monkeypatch)

    recovered = recovery.record_new_opportunities(conn, "account-a", 75)

    assert _event_tender_ids(conn) == [2]
    assert [item["tender_id"] for item in recovered] == [2]
    conn.close()


def test_recovery_must_not_reauthorize_old_profile_decision(monkeypatch):
    """A latest high decision bound to an old tenant profile is not current work."""
    conn = _conn()
    conn.execute(
        """CREATE TABLE company_profiles(
            account_id TEXT PRIMARY KEY,
            profile_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    profile_a = {"activity": "instalações elétricas", "services": ["eletricidade"]}
    profile_b = {"activity": "pintura", "services": ["pintura"]}
    conn.execute(
        "INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES (?,?,?)",
        ("account-a", json.dumps(profile_a), "2026-08-27T00:00:00+00:00"),
    )
    assert recovery.initialize_reconciliation_baseline(
        conn, "account-a", existing_account=True
    ) == 0

    _tender(conn, 3, "stale-profile")
    record_decision(
        conn,
        "TED",
        "stale-profile",
        "QUALIFIED",
        "high score under profile A",
        score=95,
        rule_version=RULE_VERSION,
        account_id="account-a",
    )

    conn.execute(
        "UPDATE company_profiles SET profile_json=?, updated_at=? WHERE account_id=?",
        (json.dumps(profile_b), "2026-08-27T00:01:00+00:00", "account-a"),
    )
    _tender(conn, 4, "current-profile")
    record_decision(
        conn,
        "TED",
        "current-profile",
        "QUALIFIED",
        "control: current profile B authority",
        score=95,
        rule_version=RULE_VERSION,
        account_id="account-a",
    )
    conn.commit()
    _disable_provider(monkeypatch)

    recovered = recovery.record_new_opportunities(conn, "account-a", 75)

    assert _event_tender_ids(conn) == [4]
    assert [item["tender_id"] for item in recovered] == [4]
    conn.close()
