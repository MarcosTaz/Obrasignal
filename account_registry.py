"""Account/tenant registry, subscription state and server-side billing gate."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import jsonify, request

from app import APP
from auth_context import configured_identity, InvalidTokenError

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


def ensure_account_table(conn):
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
    conn.commit()


def ensure_account(conn, account_id, status='active', plan='pilot'):
    ensure_account_table(conn)
    account_id = str(account_id)
    now = datetime.now(timezone.utc)
    existing = conn.execute("SELECT account_id FROM accounts WHERE account_id=?", (account_id,)).fetchone()
    if existing:
        conn.execute("UPDATE accounts SET status=? WHERE account_id=?", (status, account_id))
    else:
        trial_ends_at = (now + timedelta(days=14)).isoformat()
        conn.execute(
            """INSERT INTO accounts(account_id, status, plan, created_at, trial_ends_at, subscription_status)
               VALUES(?, ?, ?, ?, ?, 'trial')""",
            (account_id, status, plan, now.isoformat(), trial_ends_at),
        )
    conn.commit()
    _sync_revenuecat_if_due(conn, account_id)


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
    conn.commit()


def subscription_state(account):
    if not account:
        return {"plan": "none", "active": False, "source": None, "expires_at": None}
    now = datetime.now(timezone.utc)
    if account.get("plan") == "pro" and account.get("subscription_status") in {
        "active", "trial", "grace_period", "paused", "cancelled"
    }:
        expires = account.get("entitlement_expires_at")
        if not expires or _parse_iso(expires) > now:
            return {"plan": "pro", "active": True, "source": account.get("store"), "expires_at": expires}
    if account.get("plan") == "pilot":
        expires = account.get("trial_ends_at")
        if expires and _parse_iso(expires) > now:
            return {"plan": "pilot", "active": True, "source": "trial", "expires_at": expires}
    return {"plan": "expired", "active": False, "source": account.get("store"), "expires_at": account.get("entitlement_expires_at") or account.get("trial_ends_at")}


def _parse_iso(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _sync_revenuecat_if_due(conn, account_id, force=False):
    secret = (os.getenv('REVENUECAT_SECRET_API_KEY') or '').strip()
    if not secret:
        return
    row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    account = dict(row) if row else None
    if not account:
        return
    if not force and account.get('billing_synced_at'):
        age = (datetime.now(timezone.utc) - _parse_iso(account['billing_synced_at'])).total_seconds()
        expires = _parse_iso(account.get('entitlement_expires_at'))
        if age < 300 and expires - datetime.now(timezone.utc) > timedelta(hours=1):
            return
    url = 'https://api.revenuecat.com/v1/subscribers/' + str(account_id)
    req = Request(url, headers={'Authorization': f'Bearer {secret}', 'Accept': 'application/json'})
    try:
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return
    subscriber = payload.get('subscriber') or payload.get('value', {}).get('subscriber') or {}
    entitlements = subscriber.get('entitlements') or {}
    entitlement = entitlements.get(PRO_ENTITLEMENT)
    if entitlement and entitlement.get('expires_date'):
        expires = entitlement.get('expires_date')
        active = _parse_iso(expires) > datetime.now(timezone.utc)
        update_subscription(conn, account_id, plan='pro' if active else 'expired', subscription_status='active' if active else 'expired', entitlement_expires_at=expires, store=entitlement.get('store') or subscriber.get('store'), product_id=entitlement.get('product_identifier'), original_transaction_id=subscriber.get('original_app_user_id'))
    elif entitlement and entitlement.get('is_active') is True:
        update_subscription(conn, account_id, plan='pro', subscription_status='active', entitlement_expires_at=None, store=entitlement.get('store'), product_id=entitlement.get('product_identifier'))
    else:
        conn.execute("UPDATE accounts SET billing_synced_at=? WHERE account_id=?", (datetime.now(timezone.utc).isoformat(), str(account_id)))
        conn.commit()


def _sync_account_from_webhook(conn, event):
    app_user_id = event.get('app_user_id') or event.get('original_app_user_id')
    if not app_user_id:
        return
    ensure_account(conn, app_user_id)
    event_type = (event.get('type') or '').upper()
    expires_ms = event.get('expiration_at_ms')
    expires = datetime.fromtimestamp(int(expires_ms) / 1000, tz=timezone.utc).isoformat() if expires_ms else None
    store = str(event.get('store') or '').lower() or None
    product_id = event.get('product_id')
    tx = event.get('original_transaction_id') or event.get('transaction_id')
    active_events = {'INITIAL_PURCHASE', 'RENEWAL', 'UNCANCELLATION', 'PRODUCT_CHANGE', 'SUBSCRIPTION_EXTENDED', 'TRIAL_STARTED', 'TRIAL_CONVERTED'}
    if event_type in active_events:
        status = 'trial' if event_type == 'TRIAL_STARTED' else 'active'
        update_subscription(conn, app_user_id, plan='pro', subscription_status=status, entitlement_expires_at=expires, store=store, product_id=product_id, original_transaction_id=tx)
    elif event_type == 'EXPIRATION':
        update_subscription(conn, app_user_id, plan='expired', subscription_status='expired', entitlement_expires_at=expires, store=store, product_id=product_id, original_transaction_id=tx)
    elif event_type in {'CANCELLATION', 'BILLING_ISSUE'}:
        update_subscription(conn, app_user_id, plan='pro', subscription_status='cancelled' if event_type == 'CANCELLATION' else 'grace_period', entitlement_expires_at=expires, store=store, product_id=product_id, original_transaction_id=tx)


def _verify_webhook(raw_body, signature):
    secret = (os.getenv('REVENUECAT_WEBHOOK_SECRET') or '').strip()
    if not secret or not signature:
        return False
    try:
        parts = dict(item.split('=', 1) for item in signature.split(',') if '=' in item)
        timestamp = parts['t']
        received = parts['v1']
        if abs(time.time() - int(timestamp)) > 300:
            return False
        expected = hmac.new(secret.encode(), f'{timestamp}.'.encode() + raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, received)
    except (KeyError, ValueError, TypeError):
        return False


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
        return jsonify({'error': 'subscription_required', 'plan': state['plan'], 'message': 'O período de acesso terminou. Ativa o ObraSignal Pro para continuar.'}), 402
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
        account = get_account(conn, identity.account_id)
        state = subscription_state(account)
        return jsonify({**state, 'account_id': identity.account_id, 'trial_ends_at': account.get('trial_ends_at'), 'management_url': None})
    finally:
        conn.close()


@APP.post('/api/v1/billing/webhook')
def billing_webhook():
    raw = request.get_data(cache=True)
    if not _verify_webhook(raw, request.headers.get('X-RevenueCat-Webhook-Signature', '')):
        return jsonify({'error': 'invalid_signature'}), 401
    try:
        body = json.loads(raw.decode('utf-8'))
        event = body.get('event') or body
        conn = _db_from_app()
        try:
            ensure_account_table(conn)
            event_id = event.get('id') or hashlib.sha256(raw).hexdigest()
            conn.execute('CREATE TABLE IF NOT EXISTS billing_webhook_events(event_id TEXT PRIMARY KEY, received_at TEXT NOT NULL)')
            exists = conn.execute('SELECT 1 FROM billing_webhook_events WHERE event_id=?', (event_id,)).fetchone()
            if not exists:
                _sync_account_from_webhook(conn, event)
                conn.execute('INSERT INTO billing_webhook_events(event_id, received_at) VALUES(?, ?)', (event_id, datetime.now(timezone.utc).isoformat()))
                conn.commit()
        finally:
            conn.close()
        return jsonify({'ok': True})
    except Exception:
        return jsonify({'error': 'webhook_processing_failed'}), 500


def _db_from_app():
    return __import__('app').db()


def list_active_accounts(conn):
    ensure_account_table(conn)
    rows = conn.execute("SELECT account_id FROM accounts WHERE status='active' ORDER BY account_id").fetchall()
    return [row[0] for row in rows]
