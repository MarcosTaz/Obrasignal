"""Provision a distinct Supabase Auth identity for live tenant-isolation CI.

Priority:
1. anonymous provider session when the project allows it;
2. a stable ObraSignal Gmail plus-alias account using a password derived with HMAC
   from the existing E2E password (no second stored GitHub secret required).

The script never exposes either password or access token. If Supabase requires
email confirmation, it fails closed until the confirmation link is completed.
"""
import hashlib
import hmac
import json
import os
from urllib import error, parse, request

BOOTSTRAP_EMAIL = "obrasignal.pt+e2e-b@gmail.com"


def _base_and_key():
    base = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_KEY") or "").strip()
    if base.endswith("/rest/v1"):
        base = base[:-8]
    if not base or not key:
        raise SystemExit("FAIL: SUPABASE_URL and SUPABASE_KEY are required")
    return base, key


def _json_request(url, key, payload):
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"_raw": raw}
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
    signup_status, signup_data = _json_request(
        f"{base}/auth/v1/signup",
        key,
        {"email": BOOTSTRAP_EMAIL, "password": password, "data": {"purpose": "obrasignal_live_tenant_isolation"}},
    )
    session = _session(signup_data)
    if session:
        print("Using provider-authenticated password tenant B")
        return session

    token_url = f"{base}/auth/v1/token?{parse.urlencode({'grant_type': 'password'})}"
    signin_status, signin_data = _json_request(
        token_url,
        key,
        {"email": BOOTSTRAP_EMAIL, "password": password},
    )
    session = _session(signin_data)
    if session:
        print("Using existing provider-authenticated password tenant B")
        return session

    signup_code = str((signup_data or {}).get("error_code") or "")
    signin_code = str((signin_data or {}).get("error_code") or "")
    raise SystemExit(
        "FAIL: tenant B provider bootstrap did not yield an authenticated session; "
        f"signup=HTTP {signup_status}/{signup_code or 'no_session'}, "
        f"signin=HTTP {signin_status}/{signin_code or 'no_session'}. "
        f"If email confirmation is required, confirm {BOOTSTRAP_EMAIL} once and rerun."
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
