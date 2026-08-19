from datetime import datetime, timedelta, timezone
import os
import sqlite3

from account_registry import ensure_account, get_account, subscription_state, update_subscription


def db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    return conn


def test_new_account_gets_14_day_pilot():
    conn = db()
    ensure_account(conn, 'acct-billing-test')
    account = get_account(conn, 'acct-billing-test')
    state = subscription_state(account)
    assert state['plan'] == 'pilot'
    assert state['active'] is True


def test_paid_entitlement_is_not_overwritten_by_request_initialization():
    conn = db()
    ensure_account(conn, 'acct-paid')
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    update_subscription(conn, 'acct-paid', plan='pro', subscription_status='active', entitlement_expires_at=expires, store='play_store', product_id='obrasignal_pro_monthly')
    ensure_account(conn, 'acct-paid')
    state = subscription_state(get_account(conn, 'acct-paid'))
    assert state['plan'] == 'pro'
    assert state['active'] is True


def test_expired_trial_is_blocked():
    conn = db()
    ensure_account(conn, 'acct-expired')
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    conn.execute('UPDATE accounts SET trial_ends_at=? WHERE account_id=?', (past, 'acct-expired'))
    conn.commit()
    state = subscription_state(get_account(conn, 'acct-expired'))
    assert state['active'] is False
    assert state['plan'] == 'expired'
