import json
import os
import sys
import time
import uuid
from urllib import error, parse, request

API_URL = os.environ.get('API_URL', 'https://obrasignal.onrender.com/api/v1').rstrip('/')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
EMAIL_A = os.environ.get('E2E_EMAIL', '')
PASSWORD_A = os.environ.get('E2E_PASSWORD', '')
EMAIL_B = os.environ.get('E2E_EMAIL_B', '')
PASSWORD_B = os.environ.get('E2E_PASSWORD_B', '')
TARGET_BUILD = os.environ.get('TARGET_BUILD', '')


class TestFailure(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise TestFailure(message)
    return value


def http_json(url, *, method='GET', headers=None, payload=None, timeout=30, allowed=(200,)):
    body = None if payload is None else json.dumps(payload).encode('utf-8')
    req = request.Request(url, data=body, method=method)
    req.add_header('Accept', 'application/json')
    if payload is not None:
        req.add_header('Content-Type', 'application/json')
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode('utf-8')
            status = response.status
    except error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        status = exc.code
    except Exception as exc:
        raise TestFailure(f'network failure {method} {url}: {exc}') from exc
    try:
        data = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        data = {'_raw': raw}
    if status not in allowed:
        raise TestFailure(f'unexpected HTTP {status} for {method} {url}: {data}')
    return status, data


def wait_exact_build():
    require(TARGET_BUILD, 'TARGET_BUILD is required')
    deadline = time.time() + 240
    last = None
    while time.time() < deadline:
        try:
            _, health = http_json(f'{API_URL}/health', timeout=15)
            last = health.get('build') if isinstance(health, dict) else None
            if health.get('ok') is True and last == TARGET_BUILD:
                print(f'PASS exact backend build {TARGET_BUILD}')
                return
        except Exception:
            pass
        time.sleep(10)
    raise TestFailure(f'production never served exact target build {TARGET_BUILD}; last={last!r}')


def supabase_base():
    base = SUPABASE_URL
    if base.endswith('/rest/v1'):
        base = base[:-8]
    return base


def sign_in(email, password, label):
    require(SUPABASE_URL and SUPABASE_KEY, 'Missing SUPABASE_URL/SUPABASE_KEY')
    require(email and password, f'OWNER_ONLY_BLOCKER: missing dedicated production credentials for tenant {label}')
    url = f'{supabase_base()}/auth/v1/token?grant_type=password'
    _, data = http_json(
        url,
        method='POST',
        headers={'apikey': SUPABASE_KEY},
        payload={'email': email, 'password': password},
    )
    token = require(data.get('access_token'), f'tenant {label} authentication returned no access token')
    user = require(data.get('user'), f'tenant {label} authentication returned no user')
    user_id = require(user.get('id'), f'tenant {label} authentication returned no user id')
    return {'label': label, 'token': token, 'id': user_id}


def auth_headers(tenant, *, claimed_account=None):
    headers = {'Authorization': f"Bearer {tenant['token']}"}
    if claimed_account:
        headers['X-Account-Id'] = claimed_account
        headers['X-Tenant-Id'] = claimed_account
    return headers


def api_get(path, tenant, *, params=None, claimed_account=None, allowed=(200,)):
    query = dict(params or {})
    if claimed_account:
        query['account_id'] = claimed_account
        query['tenant_id'] = claimed_account
    suffix = '?' + parse.urlencode(query) if query else ''
    return http_json(
        f'{API_URL}{path}{suffix}',
        headers=auth_headers(tenant, claimed_account=claimed_account),
        allowed=allowed,
    )


def api_post(path, tenant, payload):
    return http_json(
        f'{API_URL}{path}',
        method='POST',
        headers=auth_headers(tenant),
        payload=payload,
    )


def assert_account(payload, expected_id, label):
    if not isinstance(payload, dict):
        raise TestFailure(f'{label}: response is not an object')
    actual = payload.get('account_id')
    if actual is not None and actual != expected_id:
        raise TestFailure(f'{label}: CROSS_TENANT_LEAK account_id={actual}, expected={expected_id}')


def profile_snapshot(tenant):
    _, payload = api_get('/profile', tenant)
    require(payload.get('authenticated') is True, f"{tenant['label']}: profile did not confirm authenticated state")
    require(payload.get('account_id') == tenant['id'], f"{tenant['label']}: profile account_id does not match authenticated Supabase user")
    profile = require(isinstance(payload.get('profile'), dict) and payload.get('profile'), f"{tenant['label']}: profile missing")
    return dict(profile)


def marker_profile(original, marker):
    next_profile = dict(original)
    keywords = [str(item) for item in (next_profile.get('keywords') or []) if str(item) != marker]
    next_profile['keywords'] = keywords + [marker]
    return next_profile


def assert_marker(tenant, own_marker, other_marker):
    _, payload = api_get('/profile', tenant)
    require(payload.get('account_id') == tenant['id'], f"{tenant['label']}: profile account mismatch after write")
    keywords = (payload.get('profile') or {}).get('keywords') or []
    require(own_marker in keywords, f"{tenant['label']}: own marker did not persist")
    if other_marker in keywords:
        raise TestFailure(f"{tenant['label']}: CROSS_TENANT_LEAK saw other tenant profile marker")


def adversarial_account_claim(tenant, other):
    paths = [
        ('/profile', {}),
        ('/opportunities', {'limit': 5}),
        ('/stats', {}),
        ('/workflow/stats', {}),
        ('/billing/status', {}),
    ]
    for path, params in paths:
        status, payload = api_get(path, tenant, params=params, claimed_account=other['id'], allowed=(200, 400, 401, 403, 404, 422))
        if status == 200:
            assert_account(payload, tenant['id'], f"{tenant['label']} forged-account {path}")
            if isinstance(payload, dict) and payload.get('account_id') == other['id']:
                raise TestFailure(f"{tenant['label']}: CROSS_TENANT_LEAK forged {path} returned tenant {other['label']}")
    print(f"PASS forged account/header claims cannot switch tenant {tenant['label']}→{other['label']}")


def opportunity_ids(tenant):
    _, payload = api_get('/opportunities', tenant, params={'limit': 20})
    require(payload.get('account_id') == tenant['id'], f"{tenant['label']}: opportunities account mismatch")
    items = payload.get('items') or []
    return [str(item.get('id')) for item in items if item.get('id') is not None]


def get_workflow(tenant, opportunity_id):
    status, payload = api_get(f'/opportunities/{parse.quote(opportunity_id)}/workflow', tenant, allowed=(200, 404))
    if status == 404:
        return None
    assert_account(payload, tenant['id'], f"{tenant['label']} workflow")
    workflow = payload.get('workflow') if isinstance(payload, dict) else None
    require(isinstance(workflow, dict), f"{tenant['label']}: invalid workflow envelope")
    return workflow


def set_workflow(tenant, opportunity_id, state, note):
    _, payload = api_post(f'/opportunities/{parse.quote(opportunity_id)}/workflow', tenant, {'status': state, 'note': note})
    assert_account(payload, tenant['id'], f"{tenant['label']} workflow write")
    return payload.get('workflow') or {}


def workflow_isolation(a, b):
    candidates = opportunity_ids(a) + opportunity_ids(b)
    seen = set()
    for opportunity_id in candidates:
        if opportunity_id in seen:
            continue
        seen.add(opportunity_id)
        original_a = get_workflow(a, opportunity_id)
        original_b = get_workflow(b, opportunity_id)
        if original_a is None or original_b is None:
            continue
        marker_a = f'__tenant_a_{uuid.uuid4().hex[:10]}__'
        marker_b = f'__tenant_b_{uuid.uuid4().hex[:10]}__'
        try:
            state_a = 'REVIEWING' if original_a.get('status') != 'REVIEWING' else 'PREPARING'
            state_b = 'PREPARING' if original_b.get('status') != 'PREPARING' else 'REVIEWING'
            set_workflow(a, opportunity_id, state_a, marker_a)
            after_a_from_b = get_workflow(b, opportunity_id)
            require(after_a_from_b is not None, 'tenant B workflow disappeared')
            if after_a_from_b.get('note') == marker_a:
                raise TestFailure('CROSS_TENANT_LEAK: tenant B saw tenant A workflow note')
            set_workflow(b, opportunity_id, state_b, marker_b)
            verify_a = get_workflow(a, opportunity_id)
            verify_b = get_workflow(b, opportunity_id)
            require(verify_a.get('note') == marker_a, 'tenant A workflow state was overwritten by tenant B')
            require(verify_b.get('note') == marker_b, 'tenant B workflow state did not persist independently')
            print(f'PASS live workflow isolation on opportunity {opportunity_id}')
            return
        finally:
            try:
                set_workflow(a, opportunity_id, original_a.get('status') or 'NEW', original_a.get('note'))
            except Exception as exc:
                print(f'WARNING failed to restore tenant A workflow: {exc}', file=sys.stderr)
            try:
                set_workflow(b, opportunity_id, original_b.get('status') or 'NEW', original_b.get('note'))
            except Exception as exc:
                print(f'WARNING failed to restore tenant B workflow: {exc}', file=sys.stderr)
    raise TestFailure('CUSTOMER_READY_BLOCKER: no production opportunity was accessible to both dedicated tenants, so workflow isolation could not be proven live')


def main():
    for name, value in [('SUPABASE_URL', SUPABASE_URL), ('SUPABASE_KEY', SUPABASE_KEY), ('E2E_EMAIL', EMAIL_A), ('E2E_PASSWORD', PASSWORD_A)]:
        require(value, f'Missing required secret/config: {name}')
    require(EMAIL_B and PASSWORD_B, 'OWNER_ONLY_BLOCKER: configure E2E_EMAIL_B and E2E_PASSWORD_B for a second distinct dedicated production test identity')
    wait_exact_build()
    a = sign_in(EMAIL_A, PASSWORD_A, 'A')
    b = sign_in(EMAIL_B, PASSWORD_B, 'B')
    require(a['id'] != b['id'], 'P0 TEST INVALID: tenant A and B credentials resolve to the same Supabase user')
    print('PASS two distinct authenticated production identities')

    original_a = profile_snapshot(a)
    original_b = profile_snapshot(b)
    marker_a = f'__profile_a_{uuid.uuid4().hex[:12]}__'
    marker_b = f'__profile_b_{uuid.uuid4().hex[:12]}__'
    try:
        api_post('/profile', a, marker_profile(original_a, marker_a))
        api_post('/profile', b, marker_profile(original_b, marker_b))
        assert_marker(a, marker_a, marker_b)
        assert_marker(b, marker_b, marker_a)
        print('PASS live profile persistence is isolated A/B')

        adversarial_account_claim(a, b)
        adversarial_account_claim(b, a)
        workflow_isolation(a, b)
    finally:
        try:
            api_post('/profile', a, original_a)
        except Exception as exc:
            print(f'WARNING failed to restore tenant A profile: {exc}', file=sys.stderr)
        try:
            api_post('/profile', b, original_b)
        except Exception as exc:
            print(f'WARNING failed to restore tenant B profile: {exc}', file=sys.stderr)

    print('LIVE TENANT ISOLATION PASS: no cross-tenant profile/workflow/account-claim leakage observed')


if __name__ == '__main__':
    try:
        main()
    except TestFailure as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
