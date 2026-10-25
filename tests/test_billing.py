from datetime import datetime, timedelta, timezone
import sqlite3
import pytest

from account_registry import (
    _sync_account_from_webhook,
    billing_provider_readiness,
    ensure_account,
    get_account,
    subscription_state,
    update_subscription,
)
from evaluation_policy import (
    DEFAULT_EVALUATION_DAYS, ENTERPRISE_PILOT_DAYS, MAX_VALUE_EXTENSION_DAYS,
    configure_enterprise_pilot, evaluation_metrics, grant_evaluation_extension,
    record_evaluation_event,
)

def db():
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row; return conn

def activate(conn, account_id, *, base=None):
    base=base or datetime.now(timezone.utc)
    record_evaluation_event(conn, account_id, 'profile_ready', occurred_at=base)
    record_evaluation_event(conn, account_id, 'market_data_available', occurred_at=base+timedelta(seconds=1))
    return record_evaluation_event(conn, account_id, 'first_shortlist_generated', occurred_at=base+timedelta(seconds=2))

def test_new_account_does_not_lose_days_during_onboarding():
    conn=db(); ensure_account(conn,'acct-new'); account=get_account(conn,'acct-new')
    assert account['trial_ends_at'] is None
    assert account['evaluation_activated_at'] is None
    assert account['evaluation_ends_at'] is None
    state=subscription_state(account)
    assert state['plan']=='evaluation' and state['active'] is True
    assert state['evaluation_status']=='ONBOARDING'

def test_existing_account_bootstrap_is_read_only_after_schema_is_current():
    conn=db(); ensure_account(conn,'acct-steady')
    statements=[]
    conn.set_trace_callback(statements.append)
    try:
        ensure_account(conn,'acct-steady')
        account=get_account(conn,'acct-steady')
    finally:
        conn.set_trace_callback(None)
    assert account['account_id']=='acct-steady'
    writes=[s for s in statements if s.lstrip().upper().startswith(('CREATE ','ALTER ','INSERT ','UPDATE ','DELETE ','BEGIN ','COMMIT'))]
    assert writes == []

def test_evaluation_activates_only_on_value_ready_condition_for_21_days():
    conn=db(); ensure_account(conn,'acct-eval')
    base=datetime(2026,8,25,10,0,tzinfo=timezone.utc)
    record_evaluation_event(conn,'acct-eval','profile_ready',occurred_at=base)
    record_evaluation_event(conn,'acct-eval','market_data_available',occurred_at=base+timedelta(seconds=1))
    assert get_account(conn,'acct-eval')['evaluation_activated_at'] is None
    summary=record_evaluation_event(conn,'acct-eval','first_shortlist_generated',occurred_at=base+timedelta(seconds=2))
    assert summary['status']=='EVALUATION_ACTIVE'
    start=datetime.fromisoformat(summary['activated_at'])
    end=datetime.fromisoformat(summary['ends_at'])
    assert end-start==timedelta(days=DEFAULT_EVALUATION_DAYS)
    assert summary['activation_reason']=='profile_ready+market_data_available+first_relevant_shortlist_generated'

def test_paid_entitlement_is_not_overwritten_by_request_initialization():
    conn=db(); ensure_account(conn,'acct-paid')
    expires=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat()
    update_subscription(conn,'acct-paid',plan='pro',subscription_status='active',entitlement_expires_at=expires,store='play_store',product_id='obrasignal_pro_monthly')
    ensure_account(conn,'acct-paid')
    state=subscription_state(get_account(conn,'acct-paid'))
    assert state['plan']=='pro' and state['active'] is True
    assert get_account(conn,'acct-paid')['evaluation_status']=='PAID'

def test_expired_evaluation_is_blocked():
    conn=db(); ensure_account(conn,'acct-expired'); activate(conn,'acct-expired')
    past=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    conn.execute('UPDATE accounts SET evaluation_ends_at=? WHERE account_id=?',(past,'acct-expired')); conn.commit()
    state=subscription_state(get_account(conn,'acct-expired'))
    assert state['active'] is False and state['plan']=='expired'
    assert state['evaluation_status']=='EXPIRED'

def test_extension_is_capped_and_inactive_user_is_not_eligible():
    conn=db(); ensure_account(conn,'acct-ext'); activate(conn,'acct-ext')
    with pytest.raises(ValueError,match='extension_not_eligible'):
        grant_evaluation_extension(conn,'acct-ext',days=7,reason='inactive',real_usage=False,insufficient_value_exposure=True,user_inactive=True)
    out=grant_evaluation_extension(conn,'acct-ext',days=MAX_VALUE_EXTENSION_DAYS,reason='source coverage delayed',real_usage=True,insufficient_value_exposure=True,user_inactive=False)
    assert out['extension_days']==MAX_VALUE_EXTENSION_DAYS
    with pytest.raises(ValueError,match='extension_limit_exceeded'):
        grant_evaluation_extension(conn,'acct-ext',days=1,reason='again',real_usage=True,insufficient_value_exposure=True)

def test_enterprise_pilot_is_30_days_when_explicitly_configured():
    conn=db(); ensure_account(conn,'acct-enterprise'); configure_enterprise_pilot(conn,'acct-enterprise')
    summary=activate(conn,'acct-enterprise',base=datetime(2026,8,25,10,0,tzinfo=timezone.utc))
    assert datetime.fromisoformat(summary['ends_at'])-datetime.fromisoformat(summary['activated_at'])==timedelta(days=ENTERPRISE_PILOT_DAYS)
    assert summary['type']=='enterprise'

def test_existing_legacy_account_migration_preserves_trial_state():
    conn=db()
    conn.execute('''CREATE TABLE accounts(account_id TEXT PRIMARY KEY,status TEXT NOT NULL DEFAULT 'active',plan TEXT NOT NULL DEFAULT 'pilot',created_at TEXT NOT NULL,trial_ends_at TEXT,entitlement_expires_at TEXT,store TEXT,product_id TEXT,original_transaction_id TEXT,subscription_status TEXT NOT NULL DEFAULT 'trial',billing_synced_at TEXT)''')
    end=(datetime.now(timezone.utc)+timedelta(days=5)).isoformat()
    conn.execute("INSERT INTO accounts(account_id,status,plan,created_at,trial_ends_at,subscription_status) VALUES(?,?,?,?,?,'trial')",('legacy','active','pilot',datetime.now(timezone.utc).isoformat(),end)); conn.commit()
    ensure_account(conn,'legacy'); account=get_account(conn,'legacy')
    assert account['plan']=='pilot' and account['trial_ends_at']==end
    assert account['evaluation_status'] is None
    state=subscription_state(account); assert state['plan']=='pilot' and state['active'] is True

def test_revenuecat_paid_precedence_over_unexpired_evaluation_and_metrics_are_auditable():
    conn=db(); ensure_account(conn,'acct-precedence'); activate(conn,'acct-precedence')
    expires=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat()
    update_subscription(conn,'acct-precedence',plan='pro',subscription_status='active',entitlement_expires_at=expires,store='app_store',product_id='obrasignal_pro_monthly')
    state=subscription_state(get_account(conn,'acct-precedence'))
    assert state['plan']=='pro' and state['source']=='app_store'
    metrics=evaluation_metrics(conn,get_account(conn,'acct-precedence'))
    assert metrics['TRIAL_TO_PAID']==1
    assert metrics['VALUE_EXPOSURE_RATE']==1
    assert metrics['measured_value_event_count']==0
    assert metrics['estimated_value_event_count']==0


def test_commercial_provider_readiness_requires_sync_and_hmac(monkeypatch):
    monkeypatch.delenv('REVENUECAT_SECRET_API_KEY', raising=False)
    monkeypatch.delenv('REVENUECAT_WEBHOOK_SECRET', raising=False)
    assert billing_provider_readiness() == {
        'subscriber_sync_configured': False,
        'webhook_hmac_configured': False,
        'commercial_ready': False,
    }
    monkeypatch.setenv('REVENUECAT_SECRET_API_KEY', 'secret')
    assert billing_provider_readiness()['commercial_ready'] is False
    monkeypatch.setenv('REVENUECAT_WEBHOOK_SECRET', 'hmac')
    assert billing_provider_readiness() == {
        'subscriber_sync_configured': True,
        'webhook_hmac_configured': True,
        'commercial_ready': True,
    }


def test_paused_revenuecat_subscription_stays_authorized_until_expiry():
    conn=db()
    expires_at=datetime.now(timezone.utc)+timedelta(days=3)
    _sync_account_from_webhook(conn, {
        'type': 'SUBSCRIPTION_PAUSED',
        'app_user_id': 'acct-paused',
        'expiration_at_ms': int(expires_at.timestamp()*1000),
        'store': 'stripe',
        'product_id': 'obrasignal_pro_monthly',
        'transaction_id': 'tx-pause',
    })
    account=get_account(conn,'acct-paused')
    assert account['plan']=='pro'
    assert account['subscription_status']=='paused'
    state=subscription_state(account)
    assert state['active'] is True and state['plan']=='pro'


def test_signed_but_unrelated_product_event_never_creates_pro_account():
    conn=db()
    other={'type':'INITIAL_PURCHASE','app_user_id':'acct-other',
           'entitlement_ids':['another_entitlement'],
           'product_id':'unrelated_product','event_timestamp_ms':1000}
    assert _sync_account_from_webhook(conn, other) is False
    assert get_account(conn,'acct-other') is None
    assert _sync_account_from_webhook(conn,{**other,'type':'TEST','app_user_id':'acct-test'}) is False
    assert get_account(conn,'acct-test') is None


def test_explicit_empty_entitlements_deny_pro_even_when_product_id_is_present():
    conn=db()
    event={'type':'INITIAL_PURCHASE','app_user_id':'acct-empty',
           'entitlement_ids':[],'product_id':'obrasignal_pro_monthly',
           'event_timestamp_ms':1000}
    assert _sync_account_from_webhook(conn,event) is False
    assert get_account(conn,'acct-empty') is None


def test_valid_pro_event_can_grant_paid_access_and_older_expiration_cannot_revoke_it():
    conn=db()
    expires=int((datetime.now(timezone.utc)+timedelta(days=30)).timestamp()*1000)
    base={'app_user_id':'acct-order','entitlement_ids':['pro'],
          'product_id':'price_stripe_pro','store':'stripe','expiration_at_ms':expires}
    assert _sync_account_from_webhook(conn,{**base,'type':'INITIAL_PURCHASE','event_timestamp_ms':1000}) is True
    assert _sync_account_from_webhook(conn,{**base,'type':'RENEWAL','event_timestamp_ms':3000}) is True
    assert _sync_account_from_webhook(conn,{**base,'type':'EXPIRATION','event_timestamp_ms':2000}) is False
    assert _sync_account_from_webhook(conn,{**base,'type':'EXPIRATION','event_timestamp_ms':3000}) is False
    assert _sync_account_from_webhook(conn,{**base,'type':'EXPIRATION'}) is False
    assert subscription_state(get_account(conn,'acct-order'))['plan']=='pro'


def test_latest_expiration_revokes_pro_and_old_renewal_does_not_restore_it():
    conn=db()
    future=int((datetime.now(timezone.utc)+timedelta(days=2)).timestamp()*1000)
    data={'app_user_id':'acct-expire','product_id':'obrasignal_pro_monthly',
          'expiration_at_ms':future}
    assert _sync_account_from_webhook(conn,{**data,'type':'RENEWAL','event_timestamp_ms':1000}) is True
    assert _sync_account_from_webhook(conn,{**data,'type':'EXPIRATION','event_timestamp_ms':2000}) is True
    assert _sync_account_from_webhook(conn,{**data,'type':'RENEWAL','event_timestamp_ms':1500}) is False
    assert subscription_state(get_account(conn,'acct-expire'))['plan']!='pro'


@pytest.mark.parametrize('status', ['cancelled','paused','grace_period'])
def test_terminal_subscription_state_without_expiration_cannot_be_infinite(status):
    conn=db()
    ensure_account(conn,'acct-bounded')
    update_subscription(conn,'acct-bounded',plan='pro',subscription_status=status,
                        entitlement_expires_at=None,product_id='obrasignal_pro_monthly')
    assert subscription_state(get_account(conn,'acct-bounded'))['plan']!='pro'
