import pytest

from vertical_apps.industrial_claims.billing_state import BillingStateError, BillingStateStore


def _event(event_id, event_type, *, account="tenant-a", customer="cus_test", subscription="sub_test"):
    obj = {
        "id": subscription,
        "customer": customer,
        "subscription": subscription,
        "metadata": {"certactum_account_id": account},
    }
    return {"id": event_id, "type": event_type, "data": {"object": obj}}


def test_sandbox_billing_lifecycle_success_failure_recovery_cancel_refund(tmp_path):
    store = BillingStateStore(tmp_path / "billing.sqlite3")

    checkout = store.apply_verified_event(_event("evt_checkout", "checkout.session.completed"))
    assert checkout.state == "PENDING_PAYMENT_CONFIRMATION"

    paid = store.apply_verified_event(_event("evt_paid", "invoice.paid"))
    assert paid.state == "ACTIVE"

    failed = store.apply_verified_event(_event("evt_failed", "invoice.payment_failed"))
    assert failed.state == "PAST_DUE"

    recovered = store.apply_verified_event(_event("evt_recovered", "invoice.paid"))
    assert recovered.state == "ACTIVE"

    cancelled = store.apply_verified_event(_event("evt_cancel", "customer.subscription.deleted"))
    assert cancelled.state == "CANCELLED"

    refunded = store.apply_verified_event(_event("evt_refund", "charge.refunded"))
    assert refunded.state == "REFUNDED"


def test_webhook_replay_is_idempotent_and_collision_fails_closed(tmp_path):
    store = BillingStateStore(tmp_path / "billing.sqlite3")
    original = _event("evt_1", "invoice.paid")
    first = store.apply_verified_event(original)
    replay = store.apply_verified_event(original)
    assert replay == first

    collision = _event("evt_1", "invoice.payment_failed")
    with pytest.raises(BillingStateError, match="event id collision"):
        store.apply_verified_event(collision)


def test_billing_event_requires_server_bound_certactum_account_metadata(tmp_path):
    store = BillingStateStore(tmp_path / "billing.sqlite3")
    event = _event("evt_1", "invoice.paid")
    event["data"]["object"]["metadata"] = {}
    with pytest.raises(BillingStateError, match="certactum_account_id is required"):
        store.apply_verified_event(event)


def test_unknown_event_never_changes_access_state(tmp_path):
    store = BillingStateStore(tmp_path / "billing.sqlite3")
    with pytest.raises(BillingStateError, match="unsupported billing event type"):
        store.apply_verified_event(_event("evt_unknown", "customer.created"))
