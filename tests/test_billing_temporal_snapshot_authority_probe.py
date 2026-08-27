"""Failing-before: webhook arrival order must not become paid entitlement authority."""
import sqlite3

import account_registry as billing


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    billing.ensure_account_table(conn)
    return conn


def _event(event_id, event_type, *, event_ms, expires_ms):
    return {
        "id": event_id,
        "type": event_type,
        "app_user_id": "acct-temporal",
        "original_app_user_id": "acct-temporal",
        "transaction_id": "tx-temporal",
        "original_transaction_id": "tx-temporal",
        "product_id": "obrasignal_pro_monthly",
        "entitlement_ids": [billing.PRO_ENTITLEMENT],
        "event_timestamp_ms": event_ms,
        "expiration_at_ms": expires_ms,
        "store": "play_store",
    }


def test_late_older_renewal_cannot_resurrect_newer_expiration_authority():
    """EXPIRATION(newer) -> RENEWAL(older arrival-late) must not end as paid Pro."""
    conn = _db()
    billing.ensure_account(conn, "acct-temporal")

    newer_expiration = _event(
        "evt-expiration-newer",
        "EXPIRATION",
        event_ms=2_000_000_000_000,
        expires_ms=1_999_999_999_000,
    )
    older_renewal = _event(
        "evt-renewal-older",
        "RENEWAL",
        event_ms=1_900_000_000_000,
        expires_ms=2_100_000_000_000,
    )

    billing._sync_account_from_webhook(conn, newer_expiration)
    conn.commit()
    after_expiration = billing.get_account(conn, "acct-temporal")
    # Evaluation/onboarding may independently remain active. This probe owns only
    # paid Billing authority, so prove the newer event removed Pro rather than
    # incorrectly requiring all product access to be inactive.
    assert after_expiration["plan"] == "expired"
    assert after_expiration["subscription_status"] == "expired"
    assert billing.subscription_state(after_expiration)["plan"] != "pro"

    # Webhook delivery order is not provider truth. An older event body arriving
    # later must not overwrite the already-newer entitlement observation. The
    # owner architecture may satisfy this by reconciling the current RevenueCat
    # Subscriber snapshot instead of comparing event timestamps locally.
    billing._sync_account_from_webhook(conn, older_renewal)
    conn.commit()
    final = billing.get_account(conn, "acct-temporal")

    assert final["plan"] == "expired", (
        "BILLING_TEMPORAL_AUTHORITY_BROKEN: late older RENEWAL body resurrected "
        "paid state after a newer EXPIRATION"
    )
    assert final["subscription_status"] == "expired"
    assert billing.subscription_state(final)["plan"] != "pro"
    conn.close()


def test_billing_synced_at_is_observation_metadata_not_event_authority():
    conn = _db()
    billing.ensure_account(conn, "acct-temporal")
    billing._sync_account_from_webhook(
        conn,
        _event("evt-expiration", "EXPIRATION", event_ms=2_000_000_000_000, expires_ms=1_999_999_999_000),
    )
    conn.commit()
    first = billing.get_account(conn, "acct-temporal")
    first_sync = first["billing_synced_at"]

    billing._sync_account_from_webhook(
        conn,
        _event("evt-old-renewal", "RENEWAL", event_ms=1_900_000_000_000, expires_ms=2_100_000_000_000),
    )
    conn.commit()
    final = billing.get_account(conn, "acct-temporal")

    assert first_sync is not None
    assert final["billing_synced_at"] != first_sync, "probe requires later processing metadata"
    assert final["plan"] == "expired", (
        "BILLING_PROCESSING_TIME_LAUNDERED_AS_AUTHORITY: later processing metadata "
        "coincided with an older event body becoming current paid truth"
    )
    conn.close()
