from datetime import datetime, timedelta, timezone
import sqlite3

import account_registry as billing
import app


def _iso(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _ms(days=0):
    return int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp() * 1000)


def _subscriber(*, expires_days=30, entitlement=True, period_type="normal", cancelled=False):
    if not entitlement:
        return {"entitlements": {}, "subscriptions": {}}
    expires = _iso(expires_days)
    subscription = {
        "expires_date": expires,
        "store": "play_store",
        "period_type": period_type,
    }
    if cancelled:
        subscription["unsubscribe_detected_at"] = _iso(-1)
    return {
        "entitlements": {
            billing.PRO_ENTITLEMENT: {
                "expires_date": expires,
                "product_identifier": billing.PRO_PRODUCT,
            }
        },
        "subscriptions": {billing.PRO_PRODUCT: subscription},
    }


def _event(kind, event_id, *, account_id="synthetic-company-g", event_days=0):
    return {
        "id": event_id,
        "type": kind,
        "app_user_id": account_id,
        "product_id": billing.PRO_PRODUCT,
        "entitlement_ids": [billing.PRO_ENTITLEMENT],
        "event_timestamp_ms": _ms(event_days),
        "expiration_at_ms": _ms(30),
        "purchased_at_ms": _ms(-30),
        "store": "PLAY_STORE",
        "transaction_id": f"tx-{event_id}",
        "original_transaction_id": "orig-synthetic-g",
    }


def _post(client, payload):
    return client.post(
        "/api/v1/billing/webhook",
        json={"event": payload},
        headers={"Authorization": "Bearer synthetic-webhook-secret"},
    )


def _account(database, account_id="synthetic-company-g"):
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _event_count(database, event_id):
    conn = sqlite3.connect(database)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM billing_webhook_events WHERE event_id=?", (event_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def test_synthetic_company_g_trial_active_cancelled_duplicate_stale_outage_retry_and_unpaid(monkeypatch, tmp_path):
    database = tmp_path / "company-g.db"
    monkeypatch.setattr(app, "DB", str(database))
    monkeypatch.setenv("OBRASIGNAL_DB", str(database))
    monkeypatch.setenv("REVENUECAT_WEBHOOK_AUTHORIZATION_SECRET", "synthetic-webhook-secret")
    monkeypatch.delenv("REVENUECAT_WEBHOOK_AUTHORIZATION", raising=False)
    monkeypatch.delenv("REVENUECAT_WEBHOOK_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("REVENUECAT_WEBHOOK_SECRET", raising=False)
    app.init_db()
    client = app.APP.test_client()

    provider = {"status": "ok", "subscriber": _subscriber(period_type="trial")}
    calls = []

    def fetch_snapshot(account_id):
        calls.append(account_id)
        return dict(provider)

    monkeypatch.setattr(billing, "_fetch_revenuecat_subscriber", fetch_snapshot)

    # Trial is authorized from provider snapshot, not webhook event-name inference.
    trial_event = _event("INITIAL_PURCHASE", "g-trial")
    trial = _post(client, trial_event)
    assert trial.status_code == 200
    trial_state = _account(database)
    assert trial_state["plan"] == "pro"
    assert trial_state["subscription_status"] == "trial"

    # Duplicate delivery is idempotent and cannot refetch/reproject provider state.
    calls_before_duplicate = len(calls)
    duplicate = _post(client, trial_event)
    assert duplicate.status_code == 200
    assert duplicate.get_json()["duplicate"] is True
    assert len(calls) == calls_before_duplicate
    assert _event_count(database, "g-trial") == 1

    # A current non-trial provider snapshot promotes the same account to active.
    provider["subscriber"] = _subscriber(period_type="normal")
    active = _post(client, _event("RENEWAL", "g-active", event_days=1))
    assert active.status_code == 200
    active_state = _account(database)
    assert active_state["plan"] == "pro"
    assert active_state["subscription_status"] == "active"

    # Cancellation with remaining provider entitlement remains access-active but explicitly cancelled.
    provider["subscriber"] = _subscriber(cancelled=True)
    cancelled = _post(client, _event("CANCELLATION", "g-cancelled", event_days=2))
    assert cancelled.status_code == 200
    cancelled_state = _account(database)
    assert cancelled_state["plan"] == "pro"
    assert cancelled_state["subscription_status"] == "cancelled"
    assert billing.subscription_state(cancelled_state)["active"] is True

    # Provider outage fails retryably and mutates neither paid projection nor durable acknowledgement.
    before_outage = _account(database)
    provider["status"] = "unavailable"
    provider["subscriber"] = None
    outage_event = _event("EXPIRATION", "g-outage-retry", event_days=3)
    outage = _post(client, outage_event)
    assert outage.status_code == 503
    assert _account(database) == before_outage
    assert _event_count(database, "g-outage-retry") == 0

    # Retrying the same provider event after recovery converges to current expired truth exactly once.
    provider["status"] = "ok"
    provider["subscriber"] = _subscriber(expires_days=-1)
    retry = _post(client, outage_event)
    assert retry.status_code == 200
    expired_state = _account(database)
    assert expired_state["plan"] == "expired"
    assert expired_state["subscription_status"] == "expired"
    assert _event_count(database, "g-outage-retry") == 1

    # A later-arriving but older RENEWAL body cannot resurrect access while provider truth remains expired.
    stale = _post(client, _event("RENEWAL", "g-stale-renewal", event_days=-10))
    assert stale.status_code == 200
    stale_state = _account(database)
    assert stale_state["plan"] == "expired"
    assert billing.subscription_state(stale_state)["active"] is False

    # An unpaid/unknown account with no current provider entitlement never becomes Pro.
    provider["subscriber"] = _subscriber(entitlement=False)
    unpaid = _post(
        client,
        _event("INITIAL_PURCHASE", "g-unpaid", account_id="synthetic-company-g-unpaid", event_days=4),
    )
    assert unpaid.status_code == 200
    unpaid_state = _account(database, "synthetic-company-g-unpaid")
    assert unpaid_state is None or billing.subscription_state(unpaid_state)["active"] is False
    assert _event_count(database, "g-unpaid") == 1
