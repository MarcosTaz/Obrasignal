from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import sqlite3

import pytest

import account_registry as billing
import app


def memory_db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    return conn


def iso(delta=timedelta(days=30)):
    return (datetime.now(timezone.utc) + delta).isoformat()


def ms(delta=timedelta(days=30)):
    return int((datetime.now(timezone.utc) + delta).timestamp() * 1000)


def subscriber(*, product=billing.PRO_PRODUCT, expires=None, grace=None,
               unsubscribe=False, billing_issue=False, period_type='normal',
               entitlement=True):
    expires = expires if expires is not None else iso()
    subscription = {
        'expires_date': expires,
        'grace_period_expires_date': grace,
        'store': 'play_store',
        'period_type': period_type,
        'unsubscribe_detected_at': iso(timedelta(days=-1)) if unsubscribe else None,
        'billing_issues_detected_at': iso(timedelta(days=-1)) if billing_issue else None,
    }
    return {
        'entitlements': {
            billing.PRO_ENTITLEMENT: {
                'expires_date': expires,
                'grace_period_expires_date': grace,
                'product_identifier': product,
            }
        } if entitlement else {},
        'subscriptions': {product: subscription},
    }


def event(event_type='INITIAL_PURCHASE', *, event_id=None, app_user_id='acct-pro',
          product=billing.PRO_PRODUCT, entitlements=None, expiration=None,
          event_timestamp=None):
    return {
        'id': event_id or f'evt-{event_type.lower()}-{app_user_id}',
        'type': event_type,
        'app_user_id': app_user_id,
        'product_id': product,
        'entitlement_ids': [billing.PRO_ENTITLEMENT] if entitlements is None else entitlements,
        'event_timestamp_ms': event_timestamp if event_timestamp is not None else ms(timedelta(0)),
        'purchased_at_ms': ms(timedelta(days=-1)),
        'expiration_at_ms': expiration if expiration is not None else ms(),
        'store': 'PLAY_STORE',
        'transaction_id': f'tx-{app_user_id}',
        'original_transaction_id': f'orig-{app_user_id}',
    }


@pytest.fixture
def webhook_client(monkeypatch, tmp_path):
    db_path = tmp_path / 'billing-security.db'
    monkeypatch.setattr(app, 'DB', str(db_path))
    monkeypatch.setenv('OBRASIGNAL_AUTH_MODE', 'development')
    monkeypatch.setenv('OBRASIGNAL_ACCOUNT_ID', 'billing-test-account')
    monkeypatch.setenv('REVENUECAT_WEBHOOK_AUTHORIZATION_SECRET', 'webhook-secret')
    monkeypatch.delenv('REVENUECAT_WEBHOOK_SIGNING_SECRET', raising=False)
    app.init_db()
    return app.APP.test_client(), db_path


def post_event(client, payload, authorization='Bearer webhook-secret', signature=None):
    headers = {'Authorization': authorization} if authorization is not None else {}
    if signature is not None:
        headers['X-RevenueCat-Webhook-Signature'] = signature
    return client.post('/api/v1/billing/webhook', json={'event': payload}, headers=headers)


def read_account(db_path, account_id):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute('SELECT * FROM accounts WHERE account_id=?', (account_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_events(db_path, event_id):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute('SELECT COUNT(*) FROM billing_webhook_events WHERE event_id=?', (event_id,)).fetchone()[0]
    finally:
        conn.close()


def test_revenuecat_authorization_header_is_required_and_constant_time_compared(monkeypatch):
    monkeypatch.setenv('REVENUECAT_WEBHOOK_AUTHORIZATION_SECRET', 'webhook-secret')
    monkeypatch.delenv('REVENUECAT_WEBHOOK_SIGNING_SECRET', raising=False)
    raw = b'{"event":{}}'

    assert billing._verify_webhook(raw, 'Bearer webhook-secret', '') is True
    assert billing._verify_webhook(raw, 'Bearer wrong-secret', '') is False
    assert billing._verify_webhook(raw, '', '') is False
    assert billing._verify_webhook(raw, 'Basic webhook-secret', '') is False
    assert billing._verify_webhook(raw, 'Bearer', '') is False


def test_optional_hmac_uses_revenuecat_documented_raw_body_protocol(monkeypatch):
    monkeypatch.setenv('REVENUECAT_WEBHOOK_AUTHORIZATION_SECRET', 'auth-secret')
    monkeypatch.setenv('REVENUECAT_WEBHOOK_SIGNING_SECRET', 'signing-secret')
    raw = b'{"event":{"id":"evt"}}'
    timestamp = '1700000000'
    digest = hmac.new(b'signing-secret', timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
    signature = f't={timestamp},v1={digest}'

    assert billing._verify_webhook(raw, 'Bearer auth-secret', signature, now=1700000000) is True
    assert billing._verify_webhook(raw, 'Bearer auth-secret', f't={timestamp},v1=bad', now=1700000000) is False
    assert billing._verify_webhook(raw, 'Bearer auth-secret', signature, now=1700000401) is False


def test_missing_or_malformed_pro_expiry_never_becomes_indefinite_access():
    conn = memory_db()
    billing.ensure_account(conn, 'acct-missing-expiry')
    billing.update_subscription(conn, 'acct-missing-expiry', plan='pro', subscription_status='active')
    state = billing.subscription_state(billing.get_account(conn, 'acct-missing-expiry'))
    assert state['active'] is False
    assert state['plan'] == 'expired'

    billing.ensure_account(conn, 'acct-bad-expiry')
    billing.update_subscription(conn, 'acct-bad-expiry', plan='pro', subscription_status='active', entitlement_expires_at='not-a-date')
    state = billing.subscription_state(billing.get_account(conn, 'acct-bad-expiry'))
    assert state['active'] is False
    assert state['plan'] == 'expired'


def test_google_play_base_plan_product_identity_is_accepted_but_unrelated_product_is_not():
    now = datetime.now(timezone.utc)
    good = billing._pro_snapshot(subscriber(product='obrasignal_pro_monthly:monthly'), now=now)
    bad = billing._pro_snapshot(subscriber(product='another_product'), now=now)
    assert good['active'] is True
    assert bad['active'] is False


@pytest.mark.parametrize('event_type', [
    'INITIAL_PURCHASE',
    'RENEWAL',
    'UNCANCELLATION',
    'PRODUCT_CHANGE',
    'SUBSCRIPTION_EXTENDED',
    'TRIAL_CONVERTED',
])
def test_active_subscription_events_reconcile_from_subscriber_api(webhook_client, monkeypatch, event_type):
    client, db_path = webhook_client
    account_id = f'acct-{event_type.lower()}'
    monkeypatch.setattr(billing, '_fetch_revenuecat_subscriber', lambda _account: {'status': 'ok', 'subscriber': subscriber()})

    response = post_event(client, event(event_type, app_user_id=account_id))

    assert response.status_code == 200
    account = read_account(db_path, account_id)
    assert account['plan'] == 'pro'
    assert account['subscription_status'] == 'active'
    assert billing.subscription_state(account)['active'] is True


def test_trial_started_is_paid_trial_with_real_expiry(webhook_client, monkeypatch):
    client, db_path = webhook_client
    monkeypatch.setattr(
        billing,
        '_fetch_revenuecat_subscriber',
        lambda _account: {'status': 'ok', 'subscriber': subscriber(period_type='trial')},
    )
    response = post_event(client, event('TRIAL_STARTED', app_user_id='acct-trial'))
    assert response.status_code == 200
    account = read_account(db_path, 'acct-trial')
    assert account['plan'] == 'pro'
    assert account['subscription_status'] == 'trial'
    assert billing.subscription_state(account)['active'] is True


def test_cancellation_keeps_access_until_authoritative_expiry(webhook_client, monkeypatch):
    client, db_path = webhook_client
    future = iso(timedelta(days=5))
    monkeypatch.setattr(
        billing,
        '_fetch_revenuecat_subscriber',
        lambda _account: {'status': 'ok', 'subscriber': subscriber(expires=future, unsubscribe=True)},
    )
    response = post_event(client, event('CANCELLATION', app_user_id='acct-cancel'))
    assert response.status_code == 200
    account = read_account(db_path, 'acct-cancel')
    assert account['subscription_status'] == 'cancelled'
    assert billing.subscription_state(account)['active'] is True


def test_billing_issue_uses_grace_period_boundary_not_stale_transaction_expiry(webhook_client, monkeypatch):
    client, db_path = webhook_client
    expired = iso(timedelta(hours=-1))
    grace = iso(timedelta(days=2))
    monkeypatch.setattr(
        billing,
        '_fetch_revenuecat_subscriber',
        lambda _account: {'status': 'ok', 'subscriber': subscriber(expires=expired, grace=grace, billing_issue=True)},
    )
    response = post_event(client, event('BILLING_ISSUE', app_user_id='acct-grace'))
    assert response.status_code == 200
    account = read_account(db_path, 'acct-grace')
    assert account['subscription_status'] == 'grace_period'
    assert account['entitlement_expires_at'] == grace
    assert billing.subscription_state(account)['active'] is True


def test_expiration_removes_backend_access(webhook_client, monkeypatch):
    client, db_path = webhook_client
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    billing.ensure_account(conn, 'acct-expiration')
    billing.update_subscription(conn, 'acct-expiration', plan='pro', subscription_status='active', entitlement_expires_at=iso())
    conn.close()

    monkeypatch.setattr(
        billing,
        '_fetch_revenuecat_subscriber',
        lambda _account: {'status': 'ok', 'subscriber': subscriber(expires=iso(timedelta(hours=-1)))},
    )
    response = post_event(client, event('EXPIRATION', app_user_id='acct-expiration'))
    assert response.status_code == 200
    account = read_account(db_path, 'acct-expiration')
    assert account['plan'] == 'expired'
    assert account['subscription_status'] == 'expired'
    assert billing.subscription_state(account)['active'] is False


def test_unrelated_product_and_entitlement_create_no_account_or_provider_call(webhook_client, monkeypatch):
    client, db_path = webhook_client
    calls = []
    monkeypatch.setattr(billing, '_fetch_revenuecat_subscriber', lambda account: calls.append(account) or {'status': 'ok', 'subscriber': subscriber()})

    unrelated_product = post_event(client, event(app_user_id='acct-unrelated-product', product='another_product'))
    unrelated_entitlement = post_event(client, event(app_user_id='acct-unrelated-entitlement', entitlements=['another_entitlement']))

    assert unrelated_product.status_code == 200
    assert unrelated_product.get_json()['ignored'] == 'unrelated_product'
    assert unrelated_entitlement.status_code == 200
    assert unrelated_entitlement.get_json()['ignored'] == 'unrelated_entitlement'
    assert read_account(db_path, 'acct-unrelated-product') is None
    assert read_account(db_path, 'acct-unrelated-entitlement') is None
    assert calls == []


def test_missing_app_user_id_unknown_event_and_malformed_timestamp_do_not_mutate(webhook_client, monkeypatch):
    client, db_path = webhook_client
    calls = []
    monkeypatch.setattr(billing, '_fetch_revenuecat_subscriber', lambda account: calls.append(account) or {'status': 'ok', 'subscriber': subscriber()})

    missing_user = event(app_user_id='acct-unused')
    missing_user.pop('app_user_id')
    r1 = post_event(client, missing_user)
    r2 = post_event(client, event('FUTURE_NEW_EVENT', app_user_id='acct-unknown'))
    r3 = post_event(client, event(app_user_id='acct-bad-time', event_timestamp='not-a-timestamp'))
    r4 = post_event(client, event(app_user_id='acct-no-expiry', expiration=None) | {'expiration_at_ms': None})

    assert r1.status_code == 400
    assert r2.status_code == 200 and r2.get_json()['ignored'] == 'unsupported_event_type'
    assert r3.status_code == 400
    assert r4.status_code == 400
    for account_id in ('acct-unknown', 'acct-bad-time', 'acct-no-expiry'):
        assert read_account(db_path, account_id) is None
    assert calls == []


def test_malformed_json_cannot_mutate_subscription_state(webhook_client):
    client, db_path = webhook_client
    response = client.post(
        '/api/v1/billing/webhook',
        data=b'{not-json',
        content_type='application/json',
        headers={'Authorization': 'Bearer webhook-secret'},
    )
    assert response.status_code == 400
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute('SELECT COUNT(*) FROM accounts').fetchone()[0] == 0
    finally:
        conn.close()


def test_duplicate_delivery_is_idempotent_and_does_not_refetch_provider(webhook_client, monkeypatch):
    client, db_path = webhook_client
    calls = []
    monkeypatch.setattr(
        billing,
        '_fetch_revenuecat_subscriber',
        lambda account: calls.append(account) or {'status': 'ok', 'subscriber': subscriber()},
    )
    payload = event('RENEWAL', event_id='evt-duplicate', app_user_id='acct-duplicate')
    first = post_event(client, payload)
    second = post_event(client, payload)

    assert first.status_code == 200
    assert second.status_code == 200 and second.get_json()['duplicate'] is True
    assert calls == ['acct-duplicate']
    assert count_events(db_path, 'evt-duplicate') == 1


def test_out_of_order_event_cannot_overwrite_newer_subscriber_truth(webhook_client, monkeypatch):
    client, db_path = webhook_client
    current = subscriber(expires=iso(timedelta(days=20)))
    monkeypatch.setattr(billing, '_fetch_revenuecat_subscriber', lambda _account: {'status': 'ok', 'subscriber': current})

    renewal = post_event(client, event('RENEWAL', event_id='evt-newer', app_user_id='acct-order'))
    stale_expiration = post_event(
        client,
        event('EXPIRATION', event_id='evt-older', app_user_id='acct-order', event_timestamp=ms(timedelta(days=-3)), expiration=ms(timedelta(days=-2))),
    )

    assert renewal.status_code == 200
    assert stale_expiration.status_code == 200
    account = read_account(db_path, 'acct-order')
    assert account['plan'] == 'pro'
    assert account['subscription_status'] == 'active'
    assert billing.subscription_state(account)['active'] is True


def test_subscriber_api_disagreement_wins_over_pro_claim(webhook_client, monkeypatch):
    client, db_path = webhook_client
    monkeypatch.setattr(
        billing,
        '_fetch_revenuecat_subscriber',
        lambda _account: {'status': 'ok', 'subscriber': subscriber(entitlement=False)},
    )
    response = post_event(client, event('INITIAL_PURCHASE', app_user_id='acct-disagree'))
    assert response.status_code == 200
    assert read_account(db_path, 'acct-disagree') is None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    billing.ensure_account(conn, 'acct-existing-disagree')
    billing.update_subscription(conn, 'acct-existing-disagree', plan='pro', subscription_status='active', entitlement_expires_at=iso())
    conn.close()
    response = post_event(client, event('RENEWAL', app_user_id='acct-existing-disagree'))
    assert response.status_code == 200
    assert billing.subscription_state(read_account(db_path, 'acct-existing-disagree'))['active'] is False


def test_provider_failure_is_retryable_and_never_marks_event_processed(webhook_client, monkeypatch):
    client, db_path = webhook_client
    payload = event('INITIAL_PURCHASE', event_id='evt-provider-retry', app_user_id='acct-provider')
    monkeypatch.setattr(billing, '_fetch_revenuecat_subscriber', lambda _account: {'status': 'unavailable', 'subscriber': None})
    failed = post_event(client, payload)
    assert failed.status_code == 503
    assert read_account(db_path, 'acct-provider') is None
    assert count_events(db_path, 'evt-provider-retry') == 0

    monkeypatch.setattr(billing, '_fetch_revenuecat_subscriber', lambda _account: {'status': 'ok', 'subscriber': subscriber()})
    retried = post_event(client, payload)
    assert retried.status_code == 200
    assert read_account(db_path, 'acct-provider')['plan'] == 'pro'
    assert count_events(db_path, 'evt-provider-retry') == 1


def test_forced_subscriber_reconciliation_restores_backend_pro(monkeypatch):
    conn = memory_db()
    billing.ensure_account(conn, 'acct-restore')
    monkeypatch.setattr(billing, '_fetch_revenuecat_subscriber', lambda _account: {'status': 'ok', 'subscriber': subscriber()})
    result = billing._sync_revenuecat_if_due(conn, 'acct-restore', force=True)
    assert result['status'] == 'synced'
    assert billing.subscription_state(billing.get_account(conn, 'acct-restore'))['plan'] == 'pro'


def test_backend_guard_rejects_expired_paid_state_regardless_of_client_claim(webhook_client, monkeypatch):
    client, db_path = webhook_client
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    billing.ensure_account(conn, 'acct-guard-expired')
    billing.update_subscription(
        conn,
        'acct-guard-expired',
        plan='pro',
        subscription_status='active',
        entitlement_expires_at=iso(timedelta(seconds=-1)),
    )
    conn.close()

    monkeypatch.setenv('OBRASIGNAL_ACCOUNT_ID', 'acct-guard-expired')
    response = client.get('/api/v1/opportunities', headers={'X-RevenueCat-Entitlement': 'pro'})
    assert response.status_code == 402
    assert response.get_json()['error'] == 'subscription_required'
