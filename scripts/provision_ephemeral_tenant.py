"""Provision a distinct Supabase Auth identity for live tenant-isolation CI.

Priority:
1. anonymous provider session when the project allows it;
2. server-side admin bootstrap when a Supabase secret/service-role key is present;
3. a stable ObraSignal Gmail plus-alias account using a password derived with HMAC
   from the existing E2E password (no second stored password secret required).

Admin credentials are read only from CI/server environment variables and are
never written to the browser bundle, logs, or GITHUB_ENV. The script never
exposes either password or access token. If Supabase requires email confirmation
and no admin credential is available, it fails closed.
"""
import hashlib
import hmac
import json
import os
from urllib import error, parse, request

BOOTSTRAP_EMAIL = "obrasignal.pt+e2e-b@gmail.com"
PURPOSE = "obrasignal_live_tenant_isolation"


def _base_and_key():
    base = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_KEY") or "").strip()
    if base.endswith("/rest/v1"):
        base = base[:-8]
    if not base or not key:
        raise SystemExit("FAIL: SUPABASE_URL and SUPABASE_KEY are required")
    return base, key


def _admin_key():
    return (
        (os.environ.get("SUPABASE_SECRET_KEY") or "").strip()
        or (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        or (os.environ.get("SUPABASE_ADMIN_KEY") or "").strip()
    )


def _json_request(url, key, payload=None, method="POST"):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method=method)
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"_raw": raw[:300]}
        return exc.code, data


def _session(data):
    token = str((data or {}).get("access_token") or "").strip()
    user = (data or {}).get("user") if isinstance(data, dict) else None
    user_id = str((user or {}).get("id") or "").strip()
    if token and user_id:
        return token, user_id
    return None


def _derived_password():
    source = (os.environ.get("E2E_PASSWORD") or "").encode("utf-8")
    if not source:
        raise SystemExit("FAIL: E2E_PASSWORD is required to derive tenant B bootstrap credentials")
    return hmac.new(source, b"obrasignal-live-tenant-b-v1", hashlib.sha256).hexdigest()


def _password_signin(base, key, password):
    token_url = f"{base}/auth/v1/token?{parse.urlencode({'grant_type': 'password'})}"
    status, data = _json_request(
        token_url,
        key,
        {"email": BOOTSTRAP_EMAIL, "password": password},
    )
    return status, data, _session(data)


def _admin_bootstrap(base, admin_key, password):
    """Create or repair the CI-only tenant B with confirmed email server-side."""
    status, body = _json_request(
        f"{base}/auth/v1/admin/users?page=1&per_page=1000",
        admin_key,
        None,
        method="GET",
    )
    if status != 200:
        raise SystemExit(f"FAIL: Supabase admin user listing failed with HTTP {status}")

    users = body.get("users", body if isinstance(body, list) else [])
    user = next(
        (u for u in users if str((u or {}).get("email") or "").lower() == BOOTSTRAP_EMAIL.lower()),
        None,
    )
    payload = {
        "password": password,
        "email_confirm": True,
        "user_metadata": {"purpose": PURPOSE},
    }
    if user:
        uid = str(user.get("id") or "").strip()
        if not uid:
            raise SystemExit("FAIL: Supabase admin returned tenant B without id")
        status, _ = _json_request(
            f"{base}/auth/v1/admin/users/{uid}",
            admin_key,
            payload,
            method="PUT",
        )
        if status not in (200, 201):
            raise SystemExit(f"FAIL: Supabase admin tenant B repair failed with HTTP {status}")
        print("Repaired confirmed tenant B using server-side Supabase admin credentials")
        return

    create_payload = {
        "email": BOOTSTRAP_EMAIL,
        **payload,
    }
    status, _ = _json_request(
        f"{base}/auth/v1/admin/users",
        admin_key,
        create_payload,
        method="POST",
    )
    if status not in (200, 201):
        raise SystemExit(f"FAIL: Supabase admin tenant B creation failed with HTTP {status}")
    print("Created confirmed tenant B using server-side Supabase admin credentials")


def _provider_session(base, key):
    status, data = _json_request(
        f"{base}/auth/v1/signup",
        key,
        {"data": {}, "gotrue_meta_security": {"captcha_token": None}},
    )
    session = _session(data)
    if session:
        print("Using provider-authenticated anonymous tenant B")
        return session
    code = str((data or {}).get("error_code") or "")
    if status != 422 or code != "anonymous_provider_disabled":
        print(f"Anonymous provider unavailable: HTTP {status} {code or 'unknown'}")

    password = _derived_password()
    admin_key = _admin_key()
    if admin_key:
        _admin_bootstrap(base, admin_key, password)
        signin_status, signin_data, session = _password_signin(base, key, password)
        if session:
            print("Using admin-confirmed provider-authenticated tenant B")
            return session
        signin_code = str((signin_data or {}).get("error_code") or "")
        raise SystemExit(
            "FAIL: admin-confirmed tenant B could not authenticate; "
            f"signin=HTTP {signin_status}/{signin_code or 'no_session'}"
        )

    signup_status, signup_data = _json_request(
        f"{base}/auth/v1/signup",
        key,
        {"email": BOOTSTRAP_EMAIL, "password": password, "data": {"purpose": PURPOSE}},
    )
    session = _session(signup_data)
    if session:
        print("Using provider-authenticated password tenant B")
        return session

    signin_status, signin_data, session = _password_signin(base, key, password)
    if session:
        print("Using existing provider-authenticated password tenant B")
        return session

    signup_code = str((signup_data or {}).get("error_code") or "")
    signin_code = str((signin_data or {}).get("error_code") or "")
    raise SystemExit(
        "FAIL: tenant B provider bootstrap did not yield an authenticated session; "
        f"signup=HTTP {signup_status}/{signup_code or 'no_session'}, "
        f"signin=HTTP {signin_status}/{signin_code or 'no_session'}. "
        "Configure SUPABASE_SECRET_KEY (preferred) or SUPABASE_SERVICE_ROLE_KEY as a GitHub Actions secret, "
        f"or confirm {BOOTSTRAP_EMAIL} once, then rerun."
    )


def main():
    base, key = _base_and_key()
    env_file = (os.environ.get("GITHUB_ENV") or "").strip()
    if not env_file:
        raise SystemExit("FAIL: GITHUB_ENV is required")

    token, user_id = _provider_session(base, key)
    print(f"::add-mask::{token}")
    with open(env_file, "a", encoding="utf-8") as handle:
        handle.write(f"E2E_ACCESS_TOKEN_B={token}\n")
        handle.write(f"E2E_USER_ID_B={user_id}\n")
    print(f"Provisioned distinct provider-authenticated tenant B {user_id}")


if __name__ == "__main__":
    main()
