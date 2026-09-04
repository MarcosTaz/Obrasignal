import sqlite3

import pytest

from vertical_apps.industrial_claims.billing_state import BillingStateError, BillingStateStore


def event(event_id, event_type, account="acct-1", **obj):
    payload = {"id": event_id, "type": event_type, "data": {"object": {"metadata": {"vindorum_account_id": account}, **obj}}}
    return payload


def test_vindorum_billing_schema_has_no_other_product_namespace(tmp_path):
    db = tmp_path / "billing.db"
    BillingStateStore(db)
    with sqlite3.connect(db) as connection:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "vindorum_billing_state" in names
    assert "vindorum_billing_events" in names
    assert not any("certactum" in name.lower() for name in names)


def test_checkout_completion_does_not_grant_paid_state(tmp_path):
    store = BillingStateStore(tmp_path / "billing.db")
    projected = store.apply_verified_event(event("evt-1", "checkout.session.completed", customer="cus-1"))
    assert projected.state == "PENDING_PAYMENT_CONFIRMATION"
    paid = store.apply_verified_event(event("evt-2", "invoice.paid", customer="cus-1", subscription="sub-1"))
    assert paid.state == "ACTIVE"


def test_verified_event_replay_is_idempotent_and_collision_fails(tmp_path):
    store = BillingStateStore(tmp_path / "billing.db")
    first = event("evt-1", "invoice.paid", customer="cus-1")
    assert store.apply_verified_event(first) == store.apply_verified_event(first)
    with pytest.raises(BillingStateError, match="collision"):
        store.apply_verified_event(event("evt-1", "invoice.paid", account="acct-2", customer="cus-2"))


def test_old_metadata_key_is_not_accepted(tmp_path):
    store = BillingStateStore(tmp_path / "billing.db")
    payload = {"id": "evt-x", "type": "invoice.paid", "data": {"object": {"metadata": {"certactum_account_id": "acct-x"}}}}
    with pytest.raises(BillingStateError):
        store.apply_verified_event(payload)
