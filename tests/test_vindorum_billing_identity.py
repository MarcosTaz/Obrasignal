import sqlite3

import pytest

from vertical_apps.industrial_claims.billing_state import BillingStateError, BillingStateStore


def event(event_id, event_type, account="acct-1", created=100, **obj):
    return {
        "id": event_id,
        "type": event_type,
        "created": created,
        "data": {"object": {"metadata": {"vindorum_account_id": account}, **obj}},
    }


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
    projected = store.apply_verified_event(
        event("evt-1", "checkout.session.completed", created=100, customer="cus-1", subscription="sub-1")
    )
    assert projected.state == "PENDING_PAYMENT_CONFIRMATION"
    paid = store.apply_verified_event(
        event("evt-2", "invoice.paid", created=101, customer="cus-1", subscription="sub-1")
    )
    assert paid.state == "ACTIVE"


def test_verified_event_replay_is_idempotent_and_collision_fails(tmp_path):
    store = BillingStateStore(tmp_path / "billing.db")
    first = event("evt-1", "invoice.paid", customer="cus-1", subscription="sub-1")
    assert store.apply_verified_event(first) == store.apply_verified_event(first)
    with pytest.raises(BillingStateError, match="collision"):
        store.apply_verified_event(
            event("evt-1", "invoice.paid", customer="cus-2", subscription="sub-1")
        )


def test_old_metadata_key_is_not_accepted(tmp_path):
    store = BillingStateStore(tmp_path / "billing.db")
    payload = {
        "id": "evt-x",
        "type": "invoice.paid",
        "created": 100,
        "data": {"object": {"metadata": {"certactum_account_id": "acct-x"}}},
    }
    with pytest.raises(BillingStateError):
        store.apply_verified_event(payload)


def test_stale_delivery_is_receipted_but_cannot_regress_paid_access(tmp_path):
    db = tmp_path / "billing.db"
    store = BillingStateStore(db)
    paid = store.apply_verified_event(
        event("evt-paid", "invoice.paid", created=200, customer="cus-1", subscription="sub-1")
    )
    assert paid.state == "ACTIVE"

    stale = store.apply_verified_event(
        event(
            "evt-checkout-stale",
            "checkout.session.completed",
            created=100,
            customer="cus-1",
            subscription="sub-1",
        )
    )
    assert stale == paid

    with sqlite3.connect(db) as connection:
        applied = connection.execute(
            "SELECT applied_to_projection FROM vindorum_billing_events WHERE event_id = ?",
            ("evt-checkout-stale",),
        ).fetchone()[0]
    assert applied == 0


def test_late_checkout_never_downgrades_active_same_subscription(tmp_path):
    store = BillingStateStore(tmp_path / "billing.db")
    store.apply_verified_event(
        event("evt-paid", "invoice.paid", created=100, customer="cus-1", subscription="sub-1")
    )
    projected = store.apply_verified_event(
        event(
            "evt-checkout",
            "checkout.session.completed",
            created=200,
            customer="cus-1",
            subscription="sub-1",
        )
    )
    assert projected.state == "ACTIVE"
    assert projected.last_event_id == "evt-paid"


def test_account_customer_binding_cannot_be_silently_rebound(tmp_path):
    store = BillingStateStore(tmp_path / "billing.db")
    store.apply_verified_event(
        event("evt-1", "invoice.paid", created=100, customer="cus-1", subscription="sub-1")
    )
    with pytest.raises(BillingStateError, match="customer binding mismatch"):
        store.apply_verified_event(
            event("evt-2", "invoice.paid", created=200, customer="cus-2", subscription="sub-1")
        )


def test_cancelled_subscription_cannot_be_reactivated_by_same_subscription(tmp_path):
    store = BillingStateStore(tmp_path / "billing.db")
    store.apply_verified_event(
        event("evt-paid", "invoice.paid", created=100, customer="cus-1", subscription="sub-1")
    )
    cancelled = store.apply_verified_event(
        event(
            "evt-cancel",
            "customer.subscription.deleted",
            created=200,
            customer="cus-1",
            id="sub-1",
        )
    )
    assert cancelled.state == "CANCELLED"

    ignored = store.apply_verified_event(
        event("evt-old-paid", "invoice.paid", created=300, customer="cus-1", subscription="sub-1")
    )
    assert ignored.state == "CANCELLED"

    reactivated = store.apply_verified_event(
        event("evt-new-paid", "invoice.paid", created=400, customer="cus-1", subscription="sub-2")
    )
    assert reactivated.state == "ACTIVE"
    assert reactivated.subscription_id == "sub-2"


def test_ambiguous_same_timestamp_state_change_fails_closed(tmp_path):
    store = BillingStateStore(tmp_path / "billing.db")
    store.apply_verified_event(
        event("evt-paid", "invoice.paid", created=100, customer="cus-1", subscription="sub-1")
    )
    with pytest.raises(BillingStateError, match="ambiguous same-timestamp"):
        store.apply_verified_event(
            event(
                "evt-failed",
                "invoice.payment_failed",
                created=100,
                customer="cus-1",
                subscription="sub-1",
            )
        )


def test_event_created_is_required_for_ordering(tmp_path):
    store = BillingStateStore(tmp_path / "billing.db")
    payload = event("evt-1", "invoice.paid", customer="cus-1")
    payload.pop("created")
    with pytest.raises(BillingStateError, match="event created"):
        store.apply_verified_event(payload)
