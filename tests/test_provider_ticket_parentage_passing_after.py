"""Passing-after acceptance for provider ticket -> local delivery parentage.

Synthetic SQLite + fake provider only. No network/provider/customer data.
"""
import sqlite3

import notification_events as notifications


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    notifications.ensure_event_table(conn)
    return conn


def _receipt_response(ticket_id, status="ok", *, error=None):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            receipt = {"status": status}
            if error:
                receipt["details"] = {"error": error}
            return {"data": {ticket_id: receipt}}

    return Response()


def _event(conn, account_id, key, tender_id, score=90):
    now = "2000-01-01T00:00:00+00:00"
    cur = conn.execute(
        """INSERT INTO opportunity_events(
               account_id,event_key,tender_id,source,event_type,score,created_at
           ) VALUES (?,?,?,?,?,?,?)""",
        (account_id, key, tender_id, "TED", "new_high_match", score, now),
    )
    return cur.lastrowid


def _device(conn, account_id, suffix):
    notifications.register_push_device(
        conn,
        account_id,
        f"install-parent-{suffix}",
        f"ExpoPushToken[parent-{suffix}]",
        "android",
    )
    return conn.execute(
        "SELECT id,expo_push_token FROM push_devices WHERE installation_id=?",
        (f"install-parent-{suffix}",),
    ).fetchone()


def _delivery(conn, event_id, device, ticket_id):
    now = "2000-01-01T00:00:00+00:00"
    conn.execute(
        """INSERT INTO push_deliveries(
               event_id,push_device_id,ticket_id,submitted_at,attempt_count,
               last_attempt_at,expo_push_token
           ) VALUES (?,?,?,?,1,?,?)""",
        (event_id, device["id"], ticket_id, now, now, device["expo_push_token"]),
    )
    conn.commit()


def test_duplicate_provider_ticket_fails_closed_without_consuming_receipt():
    conn = _conn()
    e1 = _event(conn, "account-a", "account-a:ted:parent-a", 101, 90)
    e2 = _event(conn, "account-a", "account-a:ted:parent-b", 102, 91)
    d1 = _device(conn, "account-a", "same-a")
    d2 = _device(conn, "account-a", "same-b")
    ticket = "provider-ticket-shared"
    _delivery(conn, e1, d1, ticket)
    _delivery(conn, e2, d2, ticket)

    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return _receipt_response(ticket)

    assert notifications.reconcile_push_receipts(
        conn, "account-a", min_age_seconds=0, post=post
    ) == 0
    assert calls == []

    rows = conn.execute(
        """SELECT receipt_status,last_error,receipt_error
           FROM push_deliveries WHERE ticket_id=? ORDER BY id""",
        (ticket,),
    ).fetchall()
    assert len(rows) == 2
    assert all(row["receipt_status"] is None for row in rows)
    assert all(row["last_error"] == "receipt_parent_ambiguous" for row in rows)
    assert all(row["receipt_error"] == "receipt_parent_ambiguous" for row in rows)
    conn.close()


def test_ticket_ambiguity_is_global_across_tenants_not_account_local():
    conn = _conn()
    e1 = _event(conn, "account-a", "account-a:ted:global-a", 201)
    e2 = _event(conn, "account-b", "account-b:ted:global-b", 202)
    d1 = _device(conn, "account-a", "global-a")
    d2 = _device(conn, "account-b", "global-b")
    ticket = "provider-ticket-cross-tenant"
    _delivery(conn, e1, d1, ticket)
    _delivery(conn, e2, d2, ticket)

    called = False

    def post(*_args, **_kwargs):
        nonlocal called
        called = True
        return _receipt_response(ticket)

    assert notifications.reconcile_push_receipts(
        conn, "account-a", min_age_seconds=0, post=post
    ) == 0
    assert called is False
    a_row = conn.execute(
        """SELECT pd.receipt_status,pd.last_error
           FROM push_deliveries pd JOIN opportunity_events e ON e.id=pd.event_id
           WHERE e.account_id='account-a'"""
    ).fetchone()
    b_row = conn.execute(
        """SELECT pd.receipt_status,pd.last_error
           FROM push_deliveries pd JOIN opportunity_events e ON e.id=pd.event_id
           WHERE e.account_id='account-b'"""
    ).fetchone()
    assert a_row["receipt_status"] is None
    assert a_row["last_error"] == "receipt_parent_ambiguous"
    # Reconciliation for A must not mutate B while still refusing the global ambiguity.
    assert b_row["receipt_status"] is None
    assert b_row["last_error"] is None
    conn.close()


def test_unique_provider_ticket_preserves_provider_acceptance_semantics():
    conn = _conn()
    event_id = _event(conn, "account-a", "account-a:ted:unique", 301)
    device = _device(conn, "account-a", "unique")
    ticket = "provider-ticket-unique"
    _delivery(conn, event_id, device, ticket)

    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return _receipt_response(ticket)

    assert notifications.reconcile_push_receipts(
        conn, "account-a", min_age_seconds=0, post=post
    ) == 1
    assert len(calls) == 1
    row = conn.execute(
        "SELECT receipt_status,last_error,receipt_error FROM push_deliveries WHERE ticket_id=?",
        (ticket,),
    ).fetchone()
    assert row["receipt_status"] == "provider_accepted"
    assert row["last_error"] is None
    assert row["receipt_error"] is None
    conn.close()
