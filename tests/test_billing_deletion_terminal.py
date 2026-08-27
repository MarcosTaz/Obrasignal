from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import account_registry as billing


PRODUCT_ID = "obrasignal_pro_monthly"


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def future_iso():
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


def future_ms():
    return int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)


def deleted(conn, account_id="acct-deleted"):
    billing.ensure_account(conn, account_id)
    conn.execute(
        """UPDATE accounts SET
           status='deleted_pending_revocation',
           plan='expired',
           subscription_status='none',
           entitlement_expires_at=NULL,
           store=NULL,
           product_id=NULL,
           original_transaction_id=NULL,
           billing_synced_at=NULL
           WHERE account_id=?""",
        (account_id,),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM accounts WHERE account_id=?", (account_id,)).fetchone())


def revenuecat_event(kind):
    return {
        "type": kind,
        "app_user_id": "acct-deleted",
        "expiration_at_ms": future_ms(),
        "store": "PLAY_STORE",
        "product_id": PRODUCT_ID,
        "original_transaction_id": "orig-late",
        "transaction_id": "tx-late",
    }


def assert_deleted_tombstone_unchanged(before, after):
    assert before["status"] == "deleted_pending_revocation"
    assert before["plan"] == "expired"
    assert before["subscription_status"] == "none"
    assert before["entitlement_expires_at"] is None
    assert before["store"] is None
    assert before["product_id"] is None
    assert before["original_transaction_id"] is None
    assert before["billing_synced_at"] is None
    assert after == before


@pytest.mark.parametrize(
    "kind",
    ["RENEWAL", "INITIAL_PURCHASE", "CANCELLATION", "BILLING_ISSUE", "EXPIRATION"],
)
def test_revenuecat_webhook_projection_cannot_mutate_deleted_pending_revocation(kind):
    conn = db()
    before = deleted(conn)

    billing._sync_account_from_webhook(conn, revenuecat_event(kind))

    after = billing.get_account(conn, "acct-deleted")
    assert_deleted_tombstone_unchanged(before, after)


def test_direct_subscription_update_cannot_repopulate_deleted_projection():
    conn = db()
    before = deleted(conn)

    billing.update_subscription(
        conn,
        "acct-deleted",
        plan="pro",
        subscription_status="active",
        entitlement_expires_at=future_iso(),
        store="play_store",
        product_id=PRODUCT_ID,
        original_transaction_id="orig-late",
    )

    after = billing.get_account(conn, "acct-deleted")
    assert_deleted_tombstone_unchanged(before, after)


def test_subscription_state_never_grants_pro_to_deleted_pending_revocation():
    conn = db()
    deleted(conn)
    conn.execute(
        """UPDATE accounts SET
           plan='pro',
           subscription_status='active',
           entitlement_expires_at=?,
           store='play_store',
           product_id=?
           WHERE account_id='acct-deleted'""",
        (future_iso(), PRODUCT_ID),
    )
    conn.commit()

    account = billing.get_account(conn, "acct-deleted")
    state = billing.subscription_state(account)

    assert account["status"] == "deleted_pending_revocation"
    assert state["active"] is False
    assert state["plan"] != "pro"
