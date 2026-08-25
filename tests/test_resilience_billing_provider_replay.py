from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import account_registry as billing


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    billing.ensure_account_table(conn)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS billing_webhook_events(event_id TEXT PRIMARY KEY, received_at TEXT NOT NULL)"
    )
    conn.commit()
    return conn


def _future(days=30):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _subscriber(*, active=True):
    expires = _future(30) if active else _future(-1)
    return {
        "entitlements": {
            billing.PRO_ENTITLEMENT: {
                "expires_date": expires,
                "product_identifier": billing.PRO_PRODUCT,
            }
        },
        "subscriptions": {
            billing.PRO_PRODUCT: {
                "expires_date": expires,
                "store": "play_store",
                "period_type": "normal",
            }
        },
    }


def _event(event_id="evt-1", kind="RENEWAL", tx="tx-1"):
    return {
        "id": event_id,
        "type": kind,
        "app_user_id": "acct-a",
        "transaction_id": tx,
        "original_transaction_id": tx,
        "product_id": billing.PRO_PRODUCT,
        "entitlement_ids": [billing.PRO_ENTITLEMENT],
        "event_timestamp_ms": 2_000_000_000_000,
        "expiration_at_ms": 2_000_086_400_000,
        "purchased_at_ms": 1_999_900_000_000,
    }


def test_subscriber_api_unavailable_preserves_local_projection(monkeypatch):
    conn = _db()
    billing.ensure_account(conn, "acct-a")
    before = billing.get_account(conn, "acct-a")
    monkeypatch.setattr(
        billing,
        "_fetch_revenuecat_subscriber",
        lambda _account_id: {"status": "unavailable", "subscriber": None},
    )

    result = billing._sync_revenuecat_if_due(conn, "acct-a", force=True)
    after = billing.get_account(conn, "acct-a")

    assert result == {"status": "unavailable", "changed": False}
    assert after == before
    assert billing.subscription_state(after)["plan"] != "pro"


def test_duplicate_trigger_does_not_make_processing_time_authoritative():
    conn = _db()
    billing.ensure_account(conn, "acct-a")
    current = _subscriber(active=True)

    first = billing._apply_revenuecat_subscriber(conn, "acct-a", current, event=_event("evt-same", "RENEWAL", "tx-new"))
    after_first = billing.get_account(conn, "acct-a")
    second = billing._apply_revenuecat_subscriber(conn, "acct-a", current, event=_event("evt-same", "RENEWAL", "tx-new"))
    after_second = billing.get_account(conn, "acct-a")

    assert first["state"] == "active"
    assert second["state"] == "active"
    assert after_second["plan"] == after_first["plan"] == "pro"
    assert after_second["subscription_status"] == after_first["subscription_status"] == "active"
    assert after_second["original_transaction_id"] == after_first["original_transaction_id"] == "tx-new"


def test_older_webhook_trigger_cannot_override_current_provider_snapshot():
    conn = _db()
    billing.ensure_account(conn, "acct-a")

    billing._apply_revenuecat_subscriber(
        conn,
        "acct-a",
        _subscriber(active=True),
        event=_event("evt-newer", "RENEWAL", "tx-current"),
    )
    result = billing._apply_revenuecat_subscriber(
        conn,
        "acct-a",
        _subscriber(active=True),
        event=_event("evt-older", "INITIAL_PURCHASE", "tx-older-trigger"),
    )
    account = billing.get_account(conn, "acct-a")

    assert result["state"] == "active"
    assert account["plan"] == "pro"
    assert account["subscription_status"] == "active"
    # The event is only a reconciliation trigger. Entitlement/current access
    # remains derived from the current Subscriber API snapshot, not event age.
    assert billing.subscription_state(account)["active"] is True


def test_projection_and_event_acknowledgement_must_not_split_on_ledger_failure():
    """FAILING-BEFORE: current #83 commits projection before event acknowledgement.

    Future passing behavior must make projection+ack atomic, or expose an explicit
    resumable state that makes identical replay deterministic. A rollback after
    ledger failure must not leave a newly granted projection with no event ack.
    """
    conn = _db()
    billing.ensure_account(conn, "acct-a")
    before = billing.get_account(conn, "acct-a")

    billing._apply_revenuecat_subscriber(
        conn,
        "acct-a",
        _subscriber(active=True),
        event=_event("evt-ambiguous", "RENEWAL", "tx-ambiguous"),
    )

    conn.execute(
        "CREATE TRIGGER fail_billing_ledger BEFORE INSERT ON billing_webhook_events "
        "BEGIN SELECT RAISE(ABORT, 'controlled ledger failure'); END"
    )
    try:
        with pytest.raises(sqlite3.IntegrityError, match="controlled ledger failure"):
            conn.execute(
                "INSERT INTO billing_webhook_events(event_id, received_at) VALUES(?, ?)",
                ("evt-ambiguous", datetime.now(timezone.utc).isoformat()),
            )
        conn.rollback()
    finally:
        conn.execute("DROP TRIGGER fail_billing_ledger")

    after = billing.get_account(conn, "acct-a")
    acknowledged = conn.execute(
        "SELECT 1 FROM billing_webhook_events WHERE event_id='evt-ambiguous'"
    ).fetchone()

    assert acknowledged is None
    # Desired invariant: failed acknowledgement cannot leave a silently committed
    # projection. This assertion intentionally fails on the current owner head.
    assert after == before
