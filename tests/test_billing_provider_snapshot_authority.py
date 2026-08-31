"""Billing owner acceptance: webhook bodies trigger, provider snapshot authorizes."""
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import account_registry as billing
import app


def iso(days=30):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def ms(days=0):
    return int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp() * 1000)


def subscriber(*, expires=None, entitlement=True, period_type='normal'):
    expires = expires if expires is not None else iso(30)
    if not entitlement:
        return {'entitlements': {}, 'subscriptions': {}}
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
                'period_type': period_type,
            }
        },
    }


def event(kind='RENEWAL', *, event_id='evt-1', account_id='acct-a', event_days=0):
    return {
        'id': event_id,
        'type': kind,
        'app_user_id': account_id,
        'product_id': billing.PRO_PRODUCT,
        'entitlement_ids': [billing.PRO_ENTITLEMENT],
        'event_timestamp_ms': ms(event_days),
        'expiration_at_ms': ms(30),
        'purchased_at_ms': ms(-30),
        'store': 'PLAY_STORE',
        'transaction_id': 'tx-a',
        'original_transaction_id': 'orig-a',
    }


@pytest.fixture
def webhook_client(monkeypatch, tmp_path):
    db_path = tmp_path / 'billing-provider-authority.db'
    monkeypatch.setattr(app, 'DB', str(db_path))
    monkeypatch.setenv('REVENUECAT_WEBHOOK_AUTHORIZATION_SECRET', 'webhook-secret')
    monkeypatch.delenv('REVENUECAT_WEBHOOK_AUTHORIZATION', raising=False)
    monkeypatch.delenv('REVENUECAT_WEBHOOK_SIGNING_SECRET', raising=False)
    monkeypatch.delenv('REVENUECAT_WEBHOOK_SECRET', raising=False)
    app.init_db()
    return app.APP.test_client(), db_path


def post(client, payload):
    return client.post(
        '/api/v1/billing/webhook',
        json={'event': payload},
        headers={'Authorization': 'Bearer webhook-secret'},
    )


def account(db_path, account_id):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute('SELECT * FROM accounts WHERE account_id=?', (account_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def event_count(db_path, event_id):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            'SELECT COUNT(*) FROM billing_webhook_events WHERE event_id=?', (event_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def seed_paid(db_path, account_id='acct-a'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        billing.ensure_account(conn, account_id)
        billing.update_subscription(
            conn, account_id, plan='pro', subscription_status='active',
            entitlement_expires_at=iso(30), store='play_store',
            product_id=billing.PRO_PRODUCT,
        )
    finally:
        conn.close()


def test_late_older_renewal_converges_to_current_provider_expired_truth(webhook_client, monkeypatch):
    client, db_path = webhook_client
    seed_paid(db_path)
    expired = subscriber(expires=iso(-1))
    monkeypatch.setattr(
        billing, '_fetch_revenuecat_subscriber',
        lambda _account: {'status': 'ok', 'subscriber': expired},
    )

    newer_expiration = post(client, event('EXPIRATION', event_id='evt-newer', event_days=0))
    older_renewal = post(client, event('RENEWAL', event_id='evt-older', event_days=-5))

    assert newer_expiration.status_code == 200
    assert older_renewal.status_code == 200
    final = account(db_path, 'acct-a')
    assert final['plan'] == 'expired'
    assert final['subscription_status'] == 'expired'
    assert billing.subscription_state(final)['plan'] != 'pro'


def test_webhook_body_disagreement_cannot_override_current_provider_snapshot(webhook_client, monkeypatch):
    client, db_path = webhook_client
    seed_paid(db_path)
    monkeypatch.setattr(
        billing, '_fetch_revenuecat_subscriber',
        lambda _account: {'status': 'ok', 'subscriber': subscriber(expires=iso(-1))},
    )

    response = post(client, event('RENEWAL', event_id='evt-body-disagrees'))

    assert response.status_code == 200
    final = account(db_path, 'acct-a')
    assert final['plan'] == 'expired'
    assert final['subscription_status'] == 'expired'


def test_provider_failure_mutates_neither_projection_nor_event_ack(webhook_client, monkeypatch):
    client, db_path = webhook_client
    seed_paid(db_path)
    before = account(db_path, 'acct-a')
    monkeypatch.setattr(
        billing, '_fetch_revenuecat_subscriber',
        lambda _account: {'status': 'unavailable', 'subscriber': None},
    )

    response = post(client, event('EXPIRATION', event_id='evt-provider-down'))

    assert response.status_code == 503
    assert account(db_path, 'acct-a') == before
    assert event_count(db_path, 'evt-provider-down') == 0


def test_existing_account_projection_and_ack_roll_back_together(webhook_client, monkeypatch):
    client, db_path = webhook_client
    seed_paid(db_path)
    before = account(db_path, 'acct-a')
    monkeypatch.setattr(
        billing, '_fetch_revenuecat_subscriber',
        lambda _account: {'status': 'ok', 'subscriber': subscriber(expires=iso(-1))},
    )
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TRIGGER fail_billing_ledger BEFORE INSERT ON billing_webhook_events "
            "BEGIN SELECT RAISE(ABORT, 'controlled ledger failure'); END"
        )
        conn.commit()
    finally:
        conn.close()

    response = post(client, event('EXPIRATION', event_id='evt-ledger-fail'))

    assert response.status_code == 500
    assert account(db_path, 'acct-a') == before
    assert event_count(db_path, 'evt-ledger-fail') == 0


def test_new_paid_account_creation_and_ack_are_atomic(webhook_client, monkeypatch):
    client, db_path = webhook_client
    monkeypatch.setattr(
        billing, '_fetch_revenuecat_subscriber',
        lambda _account: {'status': 'ok', 'subscriber': subscriber(expires=iso(30))},
    )
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TRIGGER fail_billing_ledger BEFORE INSERT ON billing_webhook_events "
            "BEGIN SELECT RAISE(ABORT, 'controlled ledger failure'); END"
        )
        conn.commit()
    finally:
        conn.close()

    response = post(client, event('INITIAL_PURCHASE', event_id='evt-new-ledger-fail', account_id='acct-new'))

    assert response.status_code == 500
    assert account(db_path, 'acct-new') is None
    assert event_count(db_path, 'evt-new-ledger-fail') == 0


def test_deletion_terminal_event_is_acknowledged_without_provider_or_resurrection(webhook_client, monkeypatch):
    client, db_path = webhook_client
    seed_paid(db_path, 'acct-deleted')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """UPDATE accounts SET status='deleted_pending_revocation', plan='expired',
               subscription_status='none', entitlement_expires_at=NULL, store=NULL,
               product_id=NULL, original_transaction_id=NULL, billing_synced_at=NULL
               WHERE account_id='acct-deleted'"""
        )
        conn.commit()
    finally:
        conn.close()
    before = account(db_path, 'acct-deleted')
    calls = []
    monkeypatch.setattr(
        billing, '_fetch_revenuecat_subscriber',
        lambda account_id: calls.append(account_id) or {'status': 'ok', 'subscriber': subscriber()},
    )

    response = post(client, event('RENEWAL', event_id='evt-deleted', account_id='acct-deleted'))

    assert response.status_code == 200
    assert response.get_json()['state'] == 'deletion_terminal'
    assert calls == []
    assert account(db_path, 'acct-deleted') == before
    assert event_count(db_path, 'evt-deleted') == 1


def test_duplicate_event_is_idempotent_and_does_not_refetch_provider(webhook_client, monkeypatch):
    client, db_path = webhook_client
    calls = []
    monkeypatch.setattr(
        billing, '_fetch_revenuecat_subscriber',
        lambda account_id: calls.append(account_id) or {'status': 'ok', 'subscriber': subscriber()},
    )
    payload = event('RENEWAL', event_id='evt-duplicate', account_id='acct-dup')

    first = post(client, payload)
    second = post(client, payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()['duplicate'] is True
    assert calls == ['acct-dup']
    assert event_count(db_path, 'evt-duplicate') == 1
