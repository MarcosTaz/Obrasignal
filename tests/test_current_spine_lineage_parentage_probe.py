"""Current-spine failing-before probes for durable Notification lineage parentage.

Synthetic SQLite and fake-provider evidence only. This file intentionally does not
prescribe owner repair representation; it proves two exact-parentage invariants on
the current integrated Safety/Privacy/Notification spine.
"""
import json
import sqlite3

from decision_log import record_decision
import notification_event_recovery as recovery
import notification_events as notifications
from opportunity_match_pipeline import RULE_VERSION


def _conn_with_tenders():
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
    return conn


def _disable_provider(monkeypatch):
    monkeypatch.setattr(notifications, "submit_pending_pushes", lambda *_a, **_k: 0)
    monkeypatch.setattr(notifications, "reconcile_push_receipts", lambda *_a, **_k: 0)


def test_current_recovery_event_keeps_exact_decision_parent_after_same_score_supersession(monkeypatch):
    """D1 -> E -> same-score D2 must leave durable E bound to D1."""
    conn = _conn_with_tenders()
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
    assert recovery.initialize_reconciliation_baseline(conn, "account-a", existing_account=True) == 0
    conn.execute(
        """INSERT INTO tenders(
               id,source,external_id,title,country,url,deadline,
               profile_reason,profile_score,score,first_seen
           ) VALUES (1,'TED','LINEAGE-D1-D2','Synthetic','PT','https://example.invalid/lineage',
                     '2099-01-01','perfil: instalações',95,95,'2026-08-27 00:00:00')"""
    )
    record_decision(
        conn,
        "TED",
        "LINEAGE-D1-D2",
        "QUALIFIED",
        "D1 current semantic authority",
        score=90,
        features={"fixture": "D1"},
        rule_version=RULE_VERSION,
        account_id="account-a",
    )
    d1 = conn.execute(
        "SELECT id FROM opportunity_decisions WHERE account_id='account-a' ORDER BY id DESC LIMIT 1"
    ).fetchone()["id"]
    conn.commit()
    _disable_provider(monkeypatch)

    created = recovery.record_new_opportunities(conn, "account-a", 75)
    assert [item["tender_id"] for item in created] == [1]

    record_decision(
        conn,
        "TED",
        "LINEAGE-D1-D2",
        "QUALIFIED",
        "D2 later current decision",
        score=90,
        features={"fixture": "D2"},
        rule_version=RULE_VERSION,
        account_id="account-a",
    )
    d2 = conn.execute(
        "SELECT id FROM opportunity_decisions WHERE account_id='account-a' ORDER BY id DESC LIMIT 1"
    ).fetchone()["id"]
    assert d2 != d1

    event = conn.execute(
        "SELECT * FROM opportunity_events WHERE account_id='account-a' AND event_type='new_high_match'"
    ).fetchone()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(opportunity_events)")}
    assert event["score"] == 90
    assert "decision_id" in columns, (
        "DECISION_EVENT_PARENTAGE_AMBIGUOUS: current recovery reads an exact decision id "
        "but durable opportunity_events drops that causal parent identity"
    )
    assert event["decision_id"] == d1
    conn.close()


def _receipt_response(ticket_id):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {ticket_id: {"status": "ok"}}}

    return Response()


def test_one_provider_ticket_cannot_authorize_two_current_local_deliveries():
    """One external receipt must not fan out into two local logical parents."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    notifications.ensure_event_table(conn)
    now = "2000-01-01T00:00:00+00:00"

    for tender_id, key, score in ((101, "ticket-a", 90), (102, "ticket-b", 91)):
        conn.execute(
            """INSERT INTO opportunity_events(
                   account_id,event_key,tender_id,source,event_type,score,created_at
               ) VALUES (?,?,?,?,?,?,?)""",
            ("account-a", f"account-a:ted:{key}", tender_id, "TED", "new_high_match", score, now),
        )

    notifications.register_push_device(
        conn, "account-a", "install-ticket-parent-a", "ExpoPushToken[ticket-parent-a]", "android"
    )
    notifications.register_push_device(
        conn, "account-a", "install-ticket-parent-b", "ExpoPushToken[ticket-parent-b]", "android"
    )
    events = conn.execute("SELECT id FROM opportunity_events ORDER BY id").fetchall()
    devices = conn.execute("SELECT id,expo_push_token FROM push_devices ORDER BY id").fetchall()
    duplicate_ticket = "provider-ticket-shared"

    for event, device in zip(events, devices):
        conn.execute(
            """INSERT INTO push_deliveries(
                   event_id,push_device_id,ticket_id,submitted_at,attempt_count,
                   last_attempt_at,expo_push_token
               ) VALUES (?,?,?,?,1,?,?)""",
            (event["id"], device["id"], duplicate_ticket, now, now, device["expo_push_token"]),
        )
    conn.commit()

    notifications.reconcile_push_receipts(
        conn,
        "account-a",
        min_age_seconds=0,
        post=lambda *_args, **_kwargs: _receipt_response(duplicate_ticket),
    )
    accepted = conn.execute(
        """SELECT event_id,push_device_id,ticket_id,receipt_status
           FROM push_deliveries WHERE receipt_status='provider_accepted' ORDER BY id"""
    ).fetchall()

    assert len(accepted) <= 1, (
        "PROVIDER_TICKET_PARENTAGE_AMBIGUOUS: one provider receipt became acceptance "
        "evidence for multiple local event/device deliveries"
    )
    conn.close()
