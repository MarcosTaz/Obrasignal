"""Provision a short-lived, distinct Supabase Auth identity for live isolation CI.

Supabase's current anonymous-auth client posts to /auth/v1/signup without an
email/password and returns a normal authenticated session.  We use the same
provider boundary directly so the CI job needs no service-role credential.
"""
import json
import os
from urllib import error, request


def main():
    base = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_KEY") or "").strip()
    env_file = (os.environ.get("GITHUB_ENV") or "").strip()
    if base.endswith("/rest/v1"):
        base = base[:-8]
    if not base or not key or not env_file:
        raise SystemExit("FAIL: SUPABASE_URL, SUPABASE_KEY and GITHUB_ENV are required")

    payload = json.dumps({"data": {}, "gotrue_meta_security": {"captcha_token": None}}).encode("utf-8")
    req = request.Request(f"{base}/auth/v1/signup", data=payload, method="POST")
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"FAIL: Supabase anonymous tenant provisioning HTTP {exc.code}: {body[:500]}") from exc
    except Exception as exc:
        raise SystemExit(f"FAIL: Supabase anonymous tenant provisioning failed: {exc}") from exc

    token = str(data.get("access_token") or "").strip()
    user = data.get("user") if isinstance(data, dict) else None
    user_id = str((user or {}).get("id") or "").strip()
    if not token or not user_id:
        raise SystemExit("FAIL: Supabase anonymous auth returned no access token/user id")

    # Mask before any later Actions step can accidentally echo the credential.
    print(f"::add-mask::{token}")
    with open(env_file, "a", encoding="utf-8") as handle:
        handle.write(f"E2E_ACCESS_TOKEN_B={token}\n")
        handle.write(f"E2E_USER_ID_B={user_id}\n")
    print(f"Provisioned provider-authenticated ephemeral tenant B {user_id}")


if __name__ == "__main__":
    main()
