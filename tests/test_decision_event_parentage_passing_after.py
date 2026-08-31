import json
import sqlite3

from decision_log import record_decision
import notification_event_recovery as recovery
import notification_events as notifications
from opportunity_match_pipeline import RULE_VERSION


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders(
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            title TEXT,
            buyer TEXT,
            country TEXT,
            url TEXT,
            deadline TEXT,
            publication_date TEXT,
            profile_reason TEXT,
            profile_score INTEGER,
            score INTEGER,
            first_seen TEXT
        )"""
    )
    notifications.ensure_event_table(conn)
    conn.execute(
        """CREATE TABLE company_profiles(
            account_id TEXT PRIMARY KEY,
            profile_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    profile = {"activity": "instalações elétricas", "services": ["eletricidade"]}
    conn.execute(
        "INSERT INTO company_profiles(account_id,profile_json,updated_at) VALUES (?,?,?)",
        ("account-a", json.dumps(profile), "2026-08-27T00:00:00+00:00"),
    )
    return conn


def test_recovered_event_retains_exact_decision_parent_after_same_score_supersession(monkeypatch):
    conn = _conn()
    assert recovery.initialize_reconciliation_baseline(conn, "account-a", existing_account=True) == 0
    conn.execute(
        """INSERT INTO tenders(
               id,source,external_id,title,country,url,deadline,
               profile_reason,profile_score,score,first_seen
           ) VALUES (1,'TED','LINEAGE-D1-D2','Synthetic','PT','https://example.invalid/lineage',
                     '2099-01-01','perfil: instalações',95,95,'2026-08-27 00:00:00')"""
    )
    record_decision(
        conn, "TED", "LINEAGE-D1-D2", "QUALIFIED", "D1",
        score=90, features={"fixture": "D1"}, rule_version=RULE_VERSION,
        account_id="account-a",
    )
    d1 = conn.execute(
        "SELECT id FROM opportunity_decisions WHERE account_id='account-a' ORDER BY id DESC LIMIT 1"
    ).fetchone()["id"]
    conn.commit()
    monkeypatch.setattr(notifications, "submit_pending_pushes", lambda *_a, **_k: 0)
    monkeypatch.setattr(notifications, "reconcile_push_receipts", lambda *_a, **_k: 0)

    created = recovery.record_new_opportunities(conn, "account-a", 75)
    assert [item["tender_id"] for item in created] == [1]
    assert created[0]["decision_id"] == d1

    record_decision(
        conn, "TED", "LINEAGE-D1-D2", "QUALIFIED", "D2",
        score=90, features={"fixture": "D2"}, rule_version=RULE_VERSION,
        account_id="account-a",
    )
    d2 = conn.execute(
        "SELECT id FROM opportunity_decisions WHERE account_id='account-a' ORDER BY id DESC LIMIT 1"
    ).fetchone()["id"]
    assert d2 != d1

    event = conn.execute(
        "SELECT * FROM opportunity_events WHERE account_id='account-a' AND event_type='new_high_match'"
    ).fetchone()
    assert event["decision_id"] == d1
    conn.close()
