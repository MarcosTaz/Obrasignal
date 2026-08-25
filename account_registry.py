"""Account/tenant registry, subscription state and server-side billing authority."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from flask import jsonify, request

from app import APP
from auth_context import configured_identity, InvalidTokenError
from evaluation_policy import (
    ensure_evaluation_schema, evaluation_access_state, evaluation_summary, evaluation_metrics,
    mark_evaluation_paid, mark_post_conversion_churn,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    plan TEXT NOT NULL DEFAULT 'pilot',
    created_at TEXT NOT NULL,
    trial_ends_at TEXT,
    entitlement_expires_at TEXT,
    store TEXT,
    product_id TEXT,
    original_transaction_id TEXT,
    subscription_status TEXT NOT NULL DEFAULT 'trial',
    billing_synced_at TEXT
)
"""
PROTECTED_PATHS = ('/api/v1/opportunities', '/api/v1/stats', '/api/v1/alerts', '/api/v1/workflow')
PRO_ENTITLEMENT = 'pro'
PRO_PRODUCT = 'obrasignal_pro_monthly'
REVENUECAT_EVENT_TYPES = frozenset({
    'INITIAL_PURCHASE',
    'TRIAL_STARTED',
    'TRIAL_CONVERTED',
    'RENEWAL',
    'UNCANCELLATION',
    'PRODUCT_CHANGE',
    'SUBSCRIPTION_EXTENDED',
    'CANCELLATION',
    'BILLING_ISSUE',
    'EXPIRATION',
})


def _now(value=None):
    return value or datetime.now(timezone.utc)


def ensure_account_table(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts'").fetchone()
    if not exists:
        conn.execute(SCHEMA)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    migrations = {
        "trial_ends_at": "ALTER TABLE accounts ADD COLUMN trial_ends_at TEXT",
        "entitlement_expires_at": "ALTER TABLE accounts ADD COLUMN entitlement_expires_at TEXT",
        "store": "ALTER TABLE accounts ADD COLUMN store TEXT",
        "product_id": "ALTER TABLE accounts ADD COLUMN product_id TEXT",
        "original_transaction_id": "ALTER TABLE accounts ADD COLUMN original_transaction_id TEXT",
        "subscription_status": "ALTER TABLE accounts ADD COLUMN subscription_status TEXT NOT NULL DEFAULT 'trial'",
        "billing_synced_at": "ALTER TABLE accounts ADD COLUMN billing_synced_at TEXT",
    }
    for name, statement in migrations.items():
        if name not in columns:
            conn.execute(statement)
    ensure_evaluation_schema(conn)
    conn.commit()


def ensure_account(conn, account_id, status='active', plan='evaluation'):
    """Ensure the tenant exists without performing network I/O.

    Authentication establishes identity; RevenueCat synchronization remains a
    separate billing concern and never runs on ordinary account bootstrap.
    """
    ensure_account_table(conn)
    account_id = str(account_id)
    now = datetime.now(timezone.utc)
    existing = conn.execute("SELECT account_id FROM accounts WHERE account_id=?", (account_id,)).fetchone()
    if existing:
        return
    conn.execute(
        """INSERT INTO accounts(account_id, status, plan, created_at, subscription_status,
           evaluation_type, evaluation_status, evaluation_value_status)
           VALUES(?, ?, ?, ?, 'none', 'self_service', 'ONBOARDING', 'EXPOSURE_PENDING')""",
        (account_id, status, plan, now.isoformat()),
    )
    conn.commit()


def get_account(conn, account_id):
    ensure_account_table(conn)
    row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    return dict(row) if row else None


def update_subscription(conn, account_id, *, plan, subscription_status,
                        entitlement_expires_at=None, store=None, product_id=None,
                        original_transaction_id=None):
    ensure_account_table(conn)
    conn.execute(
        """UPDATE accounts SET plan=?, subscription_status=?,
           entitlement_expires_at=COALESCE(?, entitlement_expires_at), billing_synced_at=?,
           store=COALESCE(?, store), product_id=COALESCE(?, product_id),
           original_transaction_id=COALESCE(?, original_transaction_id)
           WHERE account_id=?""",
        (plan, subscription_status, entitlement_expires_at, datetime.now(timezone.utc).isoformat(),
         store, product_id, original_transaction_id, str(account_id)),
    )
    if plan == 'pro' and subscription_status in {'active', 'trial', 'grace_period', 'cancelled'}:
        mark_evaluation_paid(conn, account_id)
    elif plan == 'expired' or subscription_status == 'expired':
        mark_post_conversion_churn(conn, account_id)
    conn.commit()


def subscription_state(account, *, now=None):
    """Return backend-authoritative access from persisted subscription/evaluation state.

    ObraSignal Pro is monthly. A missing or malformed entitlement expiry never
    becomes indefinite paid access.
    """
    if not account:
        return {"plan": "none", "active": False, "source": None, "expires_at": None}
    current = _now(now)
    if account.get("plan") == "pro" and account.get("subscription_status") in {
        "active", "trial", "grace_period", "cancelled"
    }:
        expires = account.get("entitlement_expires_at")
        if expires and _parse_iso(expires) > current:
            return {"plan": "pro", "active": True, "source": account.get("store"), "expires_at": expires}
    evaluation = evaluation_access_state(account, now=current)
    if evaluation is not None:
        return evaluation
    if account.get("plan") == "pilot":
        expires = account.get("trial_ends_at")
        if expires and _parse_iso(expires) > current:
            return {"plan": "pilot", "active": True, "source": "trial", "expires_at": expires}
    return {"plan": "expired", "active": False, "source": account.get("store"), "expires_at": account.get("entitlement_expires_at") or account.get("trial_ends_at")}


def _parse_iso(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_pro_product(product_id):
    value = str(product_id or '').strip()
    return value == PRO_PRODUCT or value.startswith(PRO_PRODUCT + ':')


def _fetch_revenuecat_subscriber(account_id):
    """Fetch the authoritative RevenueCat subscriber snapshot.

    Returns only bounded status categories; provider failures never mutate local
    subscription truth and never expose provider response bodies or secrets.
    """
    secret = (os.getenv('REVENUECAT_SECRET_API_KEY') or '').strip()
    if not secret:
        return {'status': 'unconfigured', 'subscriber': None}
    url = 'https://api.revenuecat.com/v1/subscribers/' + quote(str(account_id), safe='')
    req = Request(url, headers={'Authorization': f'Bearer {secret}', 'Accept': 'application/json'})
    try:
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        if exc.code == 404:
            return {'status': 'ok', 'subscriber': {}}
        return {'status': 'unavailable', 'subscriber': None}
    except (URLError, TimeoutError, ValueError, OSError, UnicodeDecodeError):
        return {'status': 'unavailable', 'subscriber': None}
    if not isinstance(payload, dict):
        return {'status': 'unavailable', 'subscriber': None}
    subscriber = payload.get('subscriber') or (payload.get('value') or {}).get('subscriber')
    if not isinstance(subscriber, dict):
        return {'status': 'unavailable', 'subscriber': None}
    return {'status': 'ok', 'subscriber': subscriber}


def _find_subscription(subscriber, product_id):
    subscriptions = subscriber.get('subscriptions') or {}
    if not isinstance(subscriptions, dict):
        return {}
    exact = subscriptions.get(product_id)
    if isinstance(exact, dict):
        return exact
    for candidate_id, record in subscriptions.items():
        if _is_pro_product(candidate_id) and isinstance(record, dict):
            return record
    return {}


def _pro_snapshot(subscriber, *, now=None):
    """Derive current Pro truth from RevenueCat's subscriber representation."""
    current = _now(now)
    entitlements = subscriber.get('entitlements') or {}
    entitlement = entitlements.get(PRO_ENTITLEMENT) if isinstance(entitlements, dict) else None
    if not isinstance(entitlement, dict):
        return {'active': False, 'status': 'expired', 'expires_at': None, 'store': None, 'product_id': None}

    product_id = entitlement.get('product_identifier')
    if not _is_pro_product(product_id):
        return {'active': False, 'status': 'expired', 'expires_at': None, 'store': None, 'product_id': product_id}

    subscription = _find_subscription(subscriber, product_id)
    expires_candidates = [
        _parse_iso(entitlement.get('expires_date')),
        _parse_iso(subscription.get('expires_date')),
    ]
    grace_candidates = [
        _parse_iso(entitlement.get('grace_period_expires_date')),
        _parse_iso(subscription.get('grace_period_expires_date')),
    ]
    expires = max(expires_candidates)
    grace = max(grace_candidates)
    access_until = max(expires, grace)
    if access_until == datetime.min.replace(tzinfo=timezone.utc) or access_until <= current:
        return {
            'active': False,
            'status': 'expired',
            'expires_at': access_until.isoformat() if access_until > datetime.min.replace(tzinfo=timezone.utc) else None,
            'store': subscription.get('store') or entitlement.get('store'),
            'product_id': product_id,
        }

    if grace > current and grace >= expires:
        status = 'grace_period'
    elif subscription.get('unsubscribe_detected_at'):
        status = 'cancelled'
    elif str(subscription.get('period_type') or '').lower() == 'trial':
        status = 'trial'
    else:
        status = 'active'
    return {
        'active': True,
        'status': status,
        'expires_at': access_until.isoformat(),
        'store': subscription.get('store') or entitlement.get('store'),
        'product_id': product_id,
    }


def _apply_revenuecat_subscriber(conn, account_id, subscriber, *, event=None, now=None):
    """Apply one authoritative subscriber snapshot to local backend state."""
    snapshot = _pro_snapshot(subscriber, now=now)
    existing = get_account(conn, account_id)
    tx = None
    if isinstance(event, dict):
        tx = event.get('original_transaction_id') or event.get('transaction_id')

    if snapshot['active']:
        if not existing:
            ensure_account(conn, account_id)
        update_subscription(
            conn,
            account_id,
            plan='pro',
            subscription_status=snapshot['status'],
            entitlement_expires_at=snapshot['expires_at'],
            store=snapshot['store'],
            product_id=snapshot['product_id'],
            original_transaction_id=tx,
        )
        return {'changed': True, 'state': snapshot['status']}

    if not existing:
        return {'changed': False, 'state': 'no_pro'}

    paid_history = existing.get('plan') == 'pro' or existing.get('evaluation_status') == 'PAID'
    if paid_history:
        update_subscription(
            conn,
            account_id,
            plan='expired',
            subscription_status='expired',
            entitlement_expires_at=snapshot['expires_at'],
            store=snapshot['store'],
            product_id=snapshot['product_id'],
            original_transaction_id=tx,
        )
        return {'changed': True, 'state': 'expired'}

    conn.execute(
        "UPDATE accounts SET billing_synced_at=? WHERE account_id=?",
        (datetime.now(timezone.utc).isoformat(), str(account_id)),
    )
    conn.commit()
    return {'changed': False, 'state': 'no_pro'}


def _sync_revenuecat_if_due(conn, account_id, force=False, *, now=None):
    current = _now(now)
    row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    account = dict(row) if row else None
    if not account:
        return {'status': 'no_account', 'changed': False}
    if not force and account.get('billing_synced_at'):
        age = (current - _parse_iso(account['billing_synced_at'])).total_seconds()
        expires = _parse_iso(account.get('entitlement_expires_at'))
        if age < 300 and expires - current > timedelta(hours=1):
            return {'status': 'cached', 'changed': False}
    provider = _fetch_revenuecat_subscriber(account_id)
    if provider['status'] != 'ok':
        return {'status': provider['status'], 'changed': False}
    applied = _apply_revenuecat_subscriber(conn, account_id, provider['subscriber'], now=current)
    return {'status': 'synced', **applied}


def _validate_ms(event, key, *, required=False):
    value = event.get(key)
    if value is None:
        return not required
    if isinstance(value, bool):
        return False
    try:
        return int(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _validate_revenuecat_event(event):
    """Classify a webhook event before any account or subscription mutation."""
    if not isinstance(event, dict):
        return {'state': 'invalid', 'reason': 'malformed_event'}
    event_type = str(event.get('type') or '').strip().upper()
    if event_type not in REVENUECAT_EVENT_TYPES:
        return {'state': 'ignored', 'reason': 'unsupported_event_type'}
    event_id = str(event.get('id') or '').strip()
    if not event_id:
        return {'state': 'invalid', 'reason': 'missing_event_id'}
    app_user_id = str(event.get('app_user_id') or '').strip()
    if not app_user_id or app_user_id.startswith('$RCAnonymousID:'):
        return {'state': 'invalid', 'reason': 'invalid_app_user_id'}
    if not _is_pro_product(event.get('product_id')):
        return {'state': 'ignored', 'reason': 'unrelated_product'}
    entitlement_ids = event.get('entitlement_ids')
    if not isinstance(entitlement_ids, list) or PRO_ENTITLEMENT not in entitlement_ids:
        return {'state': 'ignored', 'reason': 'unrelated_entitlement'}
    if not _validate_ms(event, 'event_timestamp_ms', required=True):
        return {'state': 'invalid', 'reason': 'invalid_event_timestamp'}
    if not _validate_ms(event, 'expiration_at_ms', required=True):
        return {'state': 'invalid', 'reason': 'invalid_expiration_timestamp'}
    for key in ('purchased_at_ms', 'grace_period_expiration_at_ms'):
        if not _validate_ms(event, key, required=False):
            return {'state': 'invalid', 'reason': f'invalid_{key}'}
    return {
        'state': 'relevant',
        'event_id': event_id,
        'event_type': event_type,
        'app_user_id': app_user_id,
    }


def _verify_hmac(raw_body, signature, secret, *, now=None):
    """Verify RevenueCat's documented X-RevenueCat-Webhook-Signature format."""
    if not raw_body or not signature or not secret:
        return False
    try:
        parts = dict(item.split('=', 1) for item in signature.split(',') if '=' in item)
        timestamp = parts['t']
        received = parts['v1']
        timestamp_int = int(timestamp)
        current = int(time.time() if now is None else now)
        if abs(current - timestamp_int) > 300:
            return False
        expected = hmac.new(secret.encode(), f'{timestamp}.'.encode() + raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected.encode(), received.encode())
    except (KeyError, ValueError, TypeError, OverflowError):
        return False


def _verify_webhook(raw_body, authorization, signature, *, now=None):
    """Authenticate RevenueCat using only RevenueCat-supported mechanisms.

    Production requires the configured Authorization header. Official RevenueCat
    HMAC signing is an optional second factor when a signing secret is configured.
    ``REVENUECAT_WEBHOOK_SECRET`` is accepted only as a legacy signing-secret alias.
    """
    auth_secret = (os.getenv('REVENUECAT_WEBHOOK_AUTHORIZATION_SECRET') or '').strip()
    if not auth_secret or not authorization:
        return False
    expected_auth = f'Bearer {auth_secret}'
    if not hmac.compare_digest(expected_auth.encode(), authorization.strip().encode()):
        return False

    signing_secret = (os.getenv('REVENUECAT_WEBHOOK_SIGNING_SECRET') or '').strip()
    if signing_secret:
        return _verify_hmac(raw_body, signature, signing_secret, now=now)
    return True


@APP.before_request
def _billing_guard():
    path = request.path
    if not any(path == p or path.startswith(p + '/') for p in PROTECTED_PATHS):
        return None
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return None
    conn = _db_from_app()
    try:
        ensure_account(conn, identity.account_id)
        state = subscription_state(get_account(conn, identity.account_id))
    finally:
        conn.close()
    if not state['active']:
        return jsonify({'error': 'subscription_required', 'plan': state['plan'], 'message': 'A avaliação terminou. Ativa o ObraSignal Pro para continuar.'}), 402
    return None


@APP.get('/api/v1/billing/status')
def billing_status():
    try:
        identity = configured_identity()
    except (RuntimeError, InvalidTokenError):
        return jsonify({'error': 'authentication_required'}), 401
    conn = _db_from_app()
    try:
        ensure_account(conn, identity.account_id)
        force = request.args.get('refresh') == '1'
        provider = _sync_revenuecat_if_due(conn, identity.account_id, force=force)
        account = get_account(conn, identity.account_id)
        state = subscription_state(account)
        evaluation = evaluation_summary(conn, account)
        metrics = evaluation_metrics(conn, account)
        return jsonify({
            **state,
            'account_id': identity.account_id,
            'trial_ends_at': account.get('trial_ends_at'),
            'evaluation': evaluation,
            'evaluation_metrics': metrics,
            'management_url': None,
            'provider_status': provider['status'],
        })
    finally:
        conn.close()


@APP.post('/api/v1/billing/webhook')
def billing_webhook():
    raw = request.get_data(cache=True)
    if not _verify_webhook(
        raw,
        request.headers.get('Authorization', ''),
        request.headers.get('X-RevenueCat-Webhook-Signature', ''),
    ):
        return jsonify({'error': 'invalid_webhook_authorization'}), 401
    try:
        body = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, TypeError):
        return jsonify({'error': 'invalid_webhook_payload'}), 400

    event = body.get('event') if isinstance(body, dict) else None
    classification = _validate_revenuecat_event(event)
    if classification['state'] == 'invalid':
        return jsonify({'error': classification['reason']}), 400
    if classification['state'] == 'ignored':
        return jsonify({'ok': True, 'ignored': classification['reason']})

    conn = _db_from_app()
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS billing_webhook_events(event_id TEXT PRIMARY KEY, received_at TEXT NOT NULL)')
        exists = conn.execute(
            'SELECT 1 FROM billing_webhook_events WHERE event_id=?',
            (classification['event_id'],),
        ).fetchone()
        if exists:
            return jsonify({'ok': True, 'duplicate': True})

        provider = _fetch_revenuecat_subscriber(classification['app_user_id'])
        if provider['status'] != 'ok':
            return jsonify({'error': 'billing_provider_unavailable'}), 503

        applied = _apply_revenuecat_subscriber(
            conn,
            classification['app_user_id'],
            provider['subscriber'],
            event=event,
        )
        conn.execute(
            'INSERT INTO billing_webhook_events(event_id, received_at) VALUES(?, ?)',
            (classification['event_id'], datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return jsonify({'ok': True, 'state': applied['state']})
    except Exception:
        conn.rollback()
        return jsonify({'error': 'webhook_processing_failed'}), 500
    finally:
        conn.close()


def _db_from_app():
    return __import__('app').db()


def list_active_accounts(conn):
    ensure_account_table(conn)
    rows = conn.execute("SELECT account_id FROM accounts WHERE status='active' ORDER BY account_id").fetchall()
    return [row[0] for row in rows]
