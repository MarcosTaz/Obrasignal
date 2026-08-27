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
DELETION_BILLING_TERMINAL_STATUSES = frozenset({
    'deletion_pending',
    'deletion_failed',
    'deleted_pending_revocation',
    'deleted',
})
REVENUECAT_EVENT_TYPES = frozenset({
    'INITIAL_PURCHASE',
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
    # Historical direct-helper probes need only connection-local ordering memory.
    # Keep it TEMP so no new customer-private persistent dataset is invented.
    conn.execute(
        """CREATE TEMP TABLE IF NOT EXISTS billing_event_observations(
           account_id TEXT PRIMARY KEY,
           provider_event_ms INTEGER NOT NULL,
           observed_at TEXT NOT NULL
        )"""
    )
    conn.commit()


def _insert_account_staged(conn, account_id, status='active', plan='evaluation'):
    conn.execute(
        """INSERT INTO accounts(account_id, status, plan, created_at, subscription_status,
           evaluation_type, evaluation_status, evaluation_value_status)
           VALUES(?, ?, ?, ?, 'none', 'self_service', 'ONBOARDING', 'EXPOSURE_PENDING')""",
        (str(account_id), status, plan, datetime.now(timezone.utc).isoformat()),
    )


def ensure_account(conn, account_id, status='active', plan='evaluation'):
    """Ensure the tenant exists without performing provider network I/O."""
    ensure_account_table(conn)
    account_id = str(account_id)
    existing = conn.execute("SELECT account_id FROM accounts WHERE account_id=?", (account_id,)).fetchone()
    if existing:
        return
    _insert_account_staged(conn, account_id, status=status, plan=plan)
    conn.commit()


def get_account(conn, account_id):
    ensure_account_table(conn)
    row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    return dict(row) if row else None


def _get_account_raw(conn, account_id):
    row = conn.execute("SELECT * FROM accounts WHERE account_id=?", (str(account_id),)).fetchone()
    return dict(row) if row else None


def _billing_projection_blocked(account):
    return bool(account and account.get('status') in DELETION_BILLING_TERMINAL_STATUSES)


def _write_subscription(conn, account_id, *, plan, subscription_status,
                        entitlement_expires_at=None, store=None, product_id=None,
                        original_transaction_id=None, billing_synced_at=None):
    synced_at = billing_synced_at or datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE accounts SET plan=?, subscription_status=?,
           entitlement_expires_at=COALESCE(?, entitlement_expires_at), billing_synced_at=?,
           store=COALESCE(?, store), product_id=COALESCE(?, product_id),
           original_transaction_id=COALESCE(?, original_transaction_id)
           WHERE account_id=?""",
        (
            plan, subscription_status, entitlement_expires_at, synced_at,
            store, product_id, original_transaction_id, str(account_id),
        ),
    )
    if plan == 'pro' and subscription_status in {'active', 'trial', 'grace_period', 'cancelled'}:
        mark_evaluation_paid(conn, account_id)
    elif plan == 'expired' or subscription_status == 'expired':
        mark_post_conversion_churn(conn, account_id)


def update_subscription(conn, account_id, *, plan, subscription_status,
                        entitlement_expires_at=None, store=None, product_id=None,
                        original_transaction_id=None, commit=True):
    """Project paid state unless deletion is terminal.

    Direct callers retain commit-by-default compatibility. Provider/webhook
    composition passes ``commit=False`` so projection and durable event
    acknowledgement can share one transaction.
    """
    ensure_account_table(conn)
    existing = _get_account_raw(conn, account_id)
    if _billing_projection_blocked(existing):
        return False
    _write_subscription(
        conn,
        account_id,
        plan=plan,
        subscription_status=subscription_status,
        entitlement_expires_at=entitlement_expires_at,
        store=store,
        product_id=product_id,
        original_transaction_id=original_transaction_id,
    )
    if commit:
        conn.commit()
    return True


def subscription_state(account, *, now=None):
    if not account:
        return {"plan": "none", "active": False, "source": None, "expires_at": None}
    if _billing_projection_blocked(account):
        return {"plan": "expired", "active": False, "source": None, "expires_at": None}
    current = _now(now)
    if account.get("plan") == "pro" and account.get("subscription_status") in {
        "active", "trial", "grace_period", "paused", "cancelled"
    }:
        expires = account.get("entitlement_expires_at")
        if not expires or _parse_iso(expires) > current:
            return {"plan": "pro", "active": True, "source": account.get("store"), "expires_at": expires}
    evaluation = evaluation_access_state(account, now=current)
    if evaluation is not None:
        return evaluation
    if account.get("plan") == "pilot":
        expires = account.get("trial_ends_at")
        if expires and _parse_iso(expires) > current:
            return {"plan": "pilot", "active": True, "source": "trial", "expires_at": expires}
    return {
        "plan": "expired",
        "active": False,
        "source": account.get("store"),
        "expires_at": account.get("entitlement_expires_at") or account.get("trial_ends_at"),
    }


def _parse_iso(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_pro_product(product_id):
    value = str(product_id or '').strip()
    return value == PRO_PRODUCT or value.startswith(PRO_PRODUCT + ':')


def _fetch_revenuecat_subscriber(account_id):
    """Fetch current RevenueCat subscriber truth without mutating local state."""
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
    subscriber = payload.get('subscriber')
    if subscriber is None and isinstance(payload.get('value'), dict):
        subscriber = payload['value'].get('subscriber')
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
    """Derive current Pro authority from a RevenueCat Subscriber snapshot."""
    current = _now(now)
    entitlements = subscriber.get('entitlements') or {}
    entitlement = entitlements.get(PRO_ENTITLEMENT) if isinstance(entitlements, dict) else None
    if not isinstance(entitlement, dict):
        return {'active': False, 'status': 'expired', 'expires_at': None, 'store': None, 'product_id': None}

    product_id = entitlement.get('product_identifier')
    if not _is_pro_product(product_id):
        return {'active': False, 'status': 'expired', 'expires_at': None, 'store': None, 'product_id': product_id}

    subscription = _find_subscription(subscriber, product_id)
    expires = max(
        _parse_iso(entitlement.get('expires_date')),
        _parse_iso(subscription.get('expires_date')),
    )
    grace = max(
        _parse_iso(entitlement.get('grace_period_expires_date')),
        _parse_iso(subscription.get('grace_period_expires_date')),
    )
    access_until = max(expires, grace)
    minimum = datetime.min.replace(tzinfo=timezone.utc)
    if access_until == minimum or access_until <= current:
        return {
            'active': False,
            'status': 'expired',
            'expires_at': access_until.isoformat() if access_until > minimum else None,
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


def _apply_revenuecat_subscriber(conn, account_id, subscriber, *, event=None, now=None, commit=True):
    """Project one authoritative provider snapshot.

    Webhook processing uses ``commit=False`` so authoritative projection and
    event acknowledgement commit atomically. Provider failure is handled before
    this function and therefore cannot mutate local paid truth.
    """
    ensure_account_table(conn)
    existing = _get_account_raw(conn, account_id)
    if _billing_projection_blocked(existing):
        return {'changed': False, 'state': 'deletion_terminal'}

    snapshot = _pro_snapshot(subscriber, now=now)
    tx = None
    if isinstance(event, dict):
        tx = event.get('original_transaction_id') or event.get('transaction_id')

    if snapshot['active']:
        if not existing:
            _insert_account_staged(conn, account_id)
        _write_subscription(
            conn,
            account_id,
            plan='pro',
            subscription_status=snapshot['status'],
            entitlement_expires_at=snapshot['expires_at'],
            store=snapshot['store'],
            product_id=snapshot['product_id'],
            original_transaction_id=tx,
        )
        if commit:
            conn.commit()
        return {'changed': True, 'state': snapshot['status']}

    if not existing:
        if commit:
            conn.commit()
        return {'changed': False, 'state': 'no_pro'}

    paid_history = existing.get('plan') == 'pro' or existing.get('evaluation_status') == 'PAID'
    if paid_history:
        _write_subscription(
            conn,
            account_id,
            plan='expired',
            subscription_status='expired',
            entitlement_expires_at=snapshot['expires_at'],
            store=snapshot['store'],
            product_id=snapshot['product_id'],
            original_transaction_id=tx,
        )
        if commit:
            conn.commit()
        return {'changed': True, 'state': 'expired'}

    synced_at = _next_processing_timestamp(existing.get('billing_synced_at'))
    conn.execute("UPDATE accounts SET billing_synced_at=? WHERE account_id=?", (synced_at, str(account_id)))
    if commit:
        conn.commit()
    return {'changed': False, 'state': 'no_pro'}


def _sync_revenuecat_if_due(conn, account_id, force=False, *, now=None):
    ensure_account_table(conn)
    current = _now(now)
    account = _get_account_raw(conn, account_id)
    if not account or _billing_projection_blocked(account):
        return {'status': 'no_account' if not account else 'deletion_terminal', 'changed': False}
    if not force and account.get('billing_synced_at'):
        age = (current - _parse_iso(account['billing_synced_at'])).total_seconds()
        expires = _parse_iso(account.get('entitlement_expires_at'))
        if age < 300 and expires - current > timedelta(hours=1):
            return {'status': 'cached', 'changed': False}
    provider = _fetch_revenuecat_subscriber(account_id)
    if provider['status'] != 'ok':
        return {'status': provider['status'], 'changed': False}
    applied = _apply_revenuecat_subscriber(conn, account_id, provider['subscriber'], now=current, commit=True)
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


def _event_targets_pro(event):
    if _is_pro_product(event.get('product_id')):
        return True
    if str(event.get('type') or '').strip().upper() == 'PRODUCT_CHANGE':
        return _is_pro_product(event.get('new_product_id'))
    return False


def _validate_revenuecat_event(event):
    """Classify a webhook trigger before any account/provider mutation."""
    if not isinstance(event, dict):
        return {'state': 'invalid', 'reason': 'malformed_event'}
    event_type = str(event.get('type') or '').strip().upper()
    if event_type not in REVENUECAT_EVENT_TYPES:
        return {'state': 'ignored', 'reason': 'unsupported_event_type'}
    event_id = str(event.get('id') or '').strip()
    if not event_id:
        return {'state': 'invalid', 'reason': 'missing_event_id'}
    app_user_id = str(event.get('app_user_id') or event.get('original_app_user_id') or '').strip()
    if not app_user_id or app_user_id.startswith('$RCAnonymousID:'):
        return {'state': 'invalid', 'reason': 'invalid_app_user_id'}
    if not _event_targets_pro(event):
        return {'state': 'ignored', 'reason': 'unrelated_product'}
    entitlement_ids = event.get('entitlement_ids')
    if not isinstance(entitlement_ids, list) or PRO_ENTITLEMENT not in entitlement_ids:
        return {'state': 'ignored', 'reason': 'unrelated_entitlement'}
    if not _validate_ms(event, 'event_timestamp_ms', required=True):
        return {'state': 'invalid', 'reason': 'invalid_event_timestamp'}
    return {
        'state': 'relevant',
        'event_id': event_id,
        'event_type': event_type,
        'app_user_id': app_user_id,
    }


def _next_processing_timestamp(previous):
    current = datetime.now(timezone.utc)
    prior = _parse_iso(previous)
    if prior >= current:
        current = prior + timedelta(microseconds=1)
    return current.isoformat()


def _sync_account_from_webhook(conn, event):
    """Stage the legacy event-body projection for deterministic regressions.

    Production ``billing_webhook`` never calls this helper: authenticated and
    relevant webhooks reconcile the current RevenueCat Subscriber snapshot.
    This seam remains for historical owner tests and additionally proves that
    an older provider event cannot overwrite a newer provisional observation.
    """
    app_user_id = event.get('app_user_id') or event.get('original_app_user_id')
    if not app_user_id:
        return False
    ensure_account(conn, app_user_id)
    existing = _get_account_raw(conn, app_user_id)
    if _billing_projection_blocked(existing):
        return False

    raw_event_ms = event.get('event_timestamp_ms')
    try:
        event_ms = int(raw_event_ms) if raw_event_ms is not None else None
    except (TypeError, ValueError, OverflowError):
        event_ms = None

    observation = conn.execute(
        "SELECT provider_event_ms FROM billing_event_observations WHERE account_id=?",
        (str(app_user_id),),
    ).fetchone()
    newest_ms = int(observation[0]) if observation else None

    if event_ms is not None and newest_ms is not None and event_ms < newest_ms:
        synced_at = _next_processing_timestamp(existing.get('billing_synced_at'))
        conn.execute(
            "UPDATE accounts SET billing_synced_at=? WHERE account_id=?",
            (synced_at, str(app_user_id)),
        )
        return False

    event_type = str(event.get('type') or '').upper()
    expires_ms = event.get('expiration_at_ms')
    try:
        expires = (
            datetime.fromtimestamp(int(expires_ms) / 1000, tz=timezone.utc).isoformat()
            if expires_ms else None
        )
    except (TypeError, ValueError, OverflowError, OSError):
        expires = None
    store = str(event.get('store') or '').lower() or None
    product_id = event.get('product_id')
    tx = event.get('original_transaction_id') or event.get('transaction_id')

    changed = False
    active_events = {'INITIAL_PURCHASE', 'RENEWAL', 'UNCANCELLATION', 'PRODUCT_CHANGE', 'SUBSCRIPTION_EXTENDED'}
    if event_type in active_events:
        changed = update_subscription(
            conn, app_user_id, plan='pro', subscription_status='active',
            entitlement_expires_at=expires, store=store, product_id=product_id,
            original_transaction_id=tx, commit=False,
        )
    elif event_type == 'EXPIRATION':
        changed = update_subscription(
            conn, app_user_id, plan='expired', subscription_status='expired',
            entitlement_expires_at=expires, store=store, product_id=product_id,
            original_transaction_id=tx, commit=False,
        )
    elif event_type in {'CANCELLATION', 'BILLING_ISSUE'}:
        changed = update_subscription(
            conn, app_user_id, plan='pro',
            subscription_status='cancelled' if event_type == 'CANCELLATION' else 'grace_period',
            entitlement_expires_at=expires, store=store, product_id=product_id,
            original_transaction_id=tx, commit=False,
        )

    if event_ms is not None and (newest_ms is None or event_ms >= newest_ms):
        conn.execute(
            """INSERT INTO billing_event_observations(account_id,provider_event_ms,observed_at)
               VALUES(?,?,?)
               ON CONFLICT(account_id) DO UPDATE SET
                 provider_event_ms=excluded.provider_event_ms,
                 observed_at=excluded.observed_at""",
            (str(app_user_id), event_ms, _next_processing_timestamp(existing.get('billing_synced_at'))),
        )
    return bool(changed)


def _verify_hmac(raw_body, signature, secret, *, now=None):
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


def _expected_webhook_authorization():
    full = (os.getenv('REVENUECAT_WEBHOOK_AUTHORIZATION') or '').strip()
    secret = (os.getenv('REVENUECAT_WEBHOOK_AUTHORIZATION_SECRET') or '').strip()
    derived = f'Bearer {secret}' if secret else ''
    if full and derived and not hmac.compare_digest(full.encode(), derived.encode()):
        return None
    return full or derived


def _verify_webhook(raw_body, authorization='', signature='', *, now=None):
    """Require every configured RevenueCat webhook authentication mechanism."""
    expected_authorization = _expected_webhook_authorization()
    signing_secret = (
        os.getenv('REVENUECAT_WEBHOOK_SIGNING_SECRET')
        or os.getenv('REVENUECAT_WEBHOOK_SECRET')
        or ''
    ).strip()
    if expected_authorization is None:
        return False
    if not expected_authorization and not signing_secret:
        return False
    if expected_authorization:
        if not authorization:
            return False
        if not hmac.compare_digest(expected_authorization.encode(), authorization.strip().encode()):
            return False
    if signing_secret and not _verify_hmac(raw_body, signature, signing_secret, now=now):
        return False
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
        return jsonify({
            'error': 'subscription_required',
            'plan': state['plan'],
            'message': 'A avaliação terminou. Ativa o ObraSignal Pro para continuar.',
        }), 402
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
        ensure_account_table(conn)
        conn.execute(
            'CREATE TABLE IF NOT EXISTS billing_webhook_events('
            'event_id TEXT PRIMARY KEY, received_at TEXT NOT NULL)'
        )
        exists = conn.execute(
            'SELECT 1 FROM billing_webhook_events WHERE event_id=?',
            (classification['event_id'],),
        ).fetchone()
        if exists:
            return jsonify({'ok': True, 'duplicate': True})

        existing = _get_account_raw(conn, classification['app_user_id'])
        if _billing_projection_blocked(existing):
            conn.execute(
                'INSERT INTO billing_webhook_events(event_id, received_at) VALUES(?, ?)',
                (classification['event_id'], datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            return jsonify({'ok': True, 'state': 'deletion_terminal'})

        provider = _fetch_revenuecat_subscriber(classification['app_user_id'])
        if provider['status'] != 'ok':
            conn.rollback()
            return jsonify({'error': 'billing_provider_unavailable'}), 503

        applied = _apply_revenuecat_subscriber(
            conn,
            classification['app_user_id'],
            provider['subscriber'],
            event=event,
            commit=False,
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
