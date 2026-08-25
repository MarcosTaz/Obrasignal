from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import account_registry as billing


def db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    return conn


def future():
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


def subscriber(*, active=True):
    expires = future() if active else (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    return {
        'entitlements': {
            billing.PRO_ENTITLEMENT: {
                'expires_date': expires,
                'product_identifier': billing.PRO_PRODUCT,
            }
        },
        'subscriptions': {
            billing.PRO_PRODUCT: {
                'expires_date': expires,
                'store': 'play_store',
                'period_type': 'normal',
            }
        },
    }


def deleted(conn, account_id='acct-deleted'):
    billing.ensure_account(conn, account_id)
    conn.execute(
        """UPDATE accounts SET status='deleted_pending_revocation', plan='none',
           subscription_status='none', entitlement_expires_at=NULL, store=NULL,
           product_id=NULL, original_transaction_id=NULL, billing_synced_at=NULL
           WHERE account_id=?""",
        (account_id,),
    )
    conn.commit()
    return dict(conn.execute('SELECT * FROM accounts WHERE account_id=?', (account_id,)).fetchone())


def event(kind='RENEWAL', account_id='acct-deleted'):
    return {
        'type': kind,
        'app_user_id': account_id,
        'transaction_id': 'tx-late',
        'original_transaction_id': 'orig-late',
    }


def assert_scrubbed(row):
    assert row['status'] == 'deleted_pending_revocation'
    assert row['plan'] == 'none'
    assert row['subscription_status'] == 'none'
    assert row['entitlement_expires_at'] is None
    assert row['store'] is None
    assert row['product_id'] is None
    assert row['original_transaction_id'] is None
    assert row['billing_synced_at'] is None


def test_active_snapshot_cannot_resurrect_deleted_pending_revocation():
    conn = db()
    before = deleted(conn)
    billing._apply_revenuecat_subscriber(conn, 'acct-deleted', subscriber(active=True), event=event())
    after = billing.get_account(conn, 'acct-deleted')
    assert_scrubbed(before)
    assert after == before


@pytest.mark.parametrize('active,kind', [
    (True, 'RENEWAL'),
    (True, 'RENEWAL'),
    (False, 'EXPIRATION'),
    (True, 'INITIAL_PURCHASE'),
])
def test_late_duplicate_and_out_of_order_snapshots_cannot_repopulate_scrubbed_billing(active, kind):
    conn = db()
    before = deleted(conn)
    billing._apply_revenuecat_subscriber(conn, 'acct-deleted', subscriber(active=active), event=event(kind))
    assert billing.get_account(conn, 'acct-deleted') == before


def test_direct_subscription_update_cannot_repopulate_deleted_projection_or_sync_timestamp():
    conn = db()
    before = deleted(conn)
    billing.update_subscription(
        conn,
        'acct-deleted',
        plan='pro',
        subscription_status='active',
        entitlement_expires_at=future(),
        store='play_store',
        product_id=billing.PRO_PRODUCT,
        original_transaction_id='orig-late',
    )
    assert billing.get_account(conn, 'acct-deleted') == before


def test_subscription_state_never_grants_deleted_pending_revocation_even_if_stale_paid_fields_survive():
    conn = db()
    deleted(conn)
    conn.execute(
        """UPDATE accounts SET plan='pro', subscription_status='active',
           entitlement_expires_at=?, store='play_store', product_id=?
           WHERE account_id='acct-deleted'""",
        (future(), billing.PRO_PRODUCT),
    )
    conn.commit()
    state = billing.subscription_state(billing.get_account(conn, 'acct-deleted'))
    assert state['active'] is False
    assert state['plan'] != 'pro'
