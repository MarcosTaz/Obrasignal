"""Private isolated Neon E2E with ephemeral, automatically generated test credentials.

A protected workflow injects OS_NEON_TEST_DATABASE_URL. Never output connection
details, tokens, passwords, response bodies or cookies. No customer email sent.
"""
import http.cookiejar
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid

import psycopg
import jwt

BASE = "https://ep-crimson-wildflower-b9rztglz.neonauth.c-7.eu-central-1.aws.neon.tech/obrasignal_auth/auth"
ORIGIN = "https://obrasignal.com"

def request(opener, path, data=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Accept": "application/json", "Content-Type": "application/json", "Origin": ORIGIN},
        method="POST" if data is not None else "GET",
    )
    try:
        with opener.open(req, timeout=25) as res:
            return res.status, json.load(res)
    except urllib.error.HTTPError as exc:
        return exc.code, {}

def main():
    dsn = os.getenv("OS_NEON_TEST_DATABASE_URL")
    if not dsn:
        print("BLOCKED_MISSING_NEON_TEST_DATABASE_URL")
        return 2
    email = "obrasignal-e2e-" + uuid.uuid4().hex + "@example.com"
    password = secrets.token_urlsafe(36) + "Aa1!"
    conn = psycopg.connect(dsn, connect_timeout=15)
    invited_id = None
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT public.obrasignal_issue_auth_invite(%s,%s,%s)",
                            (email, "private-github-actions-e2e", 1))
                issued = cur.fetchone()[0]
                invited_id = issued["id"]
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        status, _ = request(opener, "/sign-up/email",
                            {"email":email, "password":password,
                             "name":issued["code"]+"|Synthetic Registration"})
        if not 200 <= status < 300:
            print("INVITED_REGISTRATION_FAILED_HTTP", status)
            return 1
        print("INVITED_REGISTRATION_PASS")
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        status, payload = request(opener, "/sign-in/email", {"email":email, "password":password})
        if not 200 <= status < 300:
            print("SIGNIN_FAILED_HTTP", status)
            return 1
        print("SIGNIN_PASS")
        status, session = request(opener, "/get-session")
        if status != 200 or not isinstance(session,dict) or (
           session.get("user") or {}).get("email","").lower() != email:
            print("SESSION_IDENTITY_FAILED_HTTP", status)
            return 1
        print("SESSION_IDENTITY_PASS")
        status, token_result = request(opener, "/token")
        candidate = token_result.get("token") if isinstance(token_result, dict) else None
        if status != 200 or not isinstance(candidate, str) or candidate.count(".") != 2:
            print("NEON_JWT_ENDPOINT_NOT_PROVEN", status)
            return 1
        try:
            keyset = jwt.PyJWKClient(BASE + "/.well-known/jwks.json")
            key = keyset.get_signing_key_from_jwt(candidate)
            verified = jwt.decode(candidate, key.key, algorithms=["RS256", "ES256", "EdDSA"], issuer=BASE,
                                  options={"verify_aud": False, "require": ["exp", "iat", "iss", "sub"]})
        except jwt.InvalidIssuerError:
            # Signature is verified against the isolated Neon JWKS before inspecting issuer.
            try:
                verified_without_issuer = jwt.decode(
                    candidate, key.key, algorithms=["RS256", "ES256", "EdDSA"],
                    options={"verify_aud": False, "verify_iss": False,
                             "require": ["exp", "iat", "iss", "sub"]})
                actual = urlsplit(verified_without_issuer["iss"])
                expected = urlsplit(BASE)
                if actual.scheme != "https" or actual.hostname != expected.hostname:
                    print("NEON_JWT_ISSUER_OUTSIDE_TRUSTED_AUTH_HOST")
                    return 1
                print("NEON_JWT_ISSUER_HOST_MATCHES_AUTH_PROVIDER")
                print("NEON_JWT_ISSUER_PATH_MATCHES_BASE", actual.path == expected.path)
                print("NEON_JWT_ISSUER_PATH_SUFFIX_AUTH", actual.path.endswith("/auth"))
                print("NEON_JWT_ISSUER_PATH_SUFFIX_JWT", actual.path.endswith("/jwt"))
                print("NEON_JWT_ISSUER_PATH_CATEGORY", "root" if actual.path in ("", "/") else "provider_prefix" if actual.path.startswith("/obrasignal_auth") else "other")
                print("NEON_JWT_ISSUER_HAS_QUERY", bool(actual.query))
                print("NEON_JWT_ISSUER_HAS_PORT", actual.port is not None)
            except (jwt.PyJWTError, ValueError, KeyError):
                print("NEON_JWT_ISSUER_DIAGNOSTIC_FAILED")
            return 1
        except (jwt.PyJWTError, ValueError) as exc:
            # Diagnose without printing actual tokens, provider URLs or claims.
            if isinstance(exc, jwt.InvalidIssuerError):
                print("NEON_JWT_ISSUER_MISMATCH")
            elif isinstance(exc, jwt.InvalidSignatureError):
                print("NEON_JWT_SIGNATURE_INVALID")
            elif isinstance(exc, jwt.PyJWKClientError):
                print("NEON_JWT_SIGNING_KEY_UNAVAILABLE")
            elif isinstance(exc, jwt.MissingRequiredClaimError):
                print("NEON_JWT_REQUIRED_CLAIM_MISSING")
            elif isinstance(exc, jwt.InvalidAlgorithmError):
                print("NEON_JWT_ALGORITHM_UNSUPPORTED")
            else:
                print("NEON_JWT_VERIFICATION_FAILED")
            return 1
        if str(verified.get("sub")) != str(session["user"].get("id")):
            print("NEON_JWT_SUBJECT_MISMATCH")
            return 1
        print("NEON_JWT_SIGNATURE_ISSUER_SUBJECT_PASS")
        print("NEON_JWT_AUDIENCE_PRESENT", bool(verified.get("aud")))

        wrong = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        status, _ = request(wrong, "/sign-in/email", {"email":email,"password":password+"wrong"})
        if 200 <= status < 300:
            print("WRONG_PASSWORD_SECURITY_FAILURE")
            return 1
        print("WRONG_PASSWORD_DENIAL_PASS")
        return 0
    finally:
        # Clean up ONLY this newly generated isolated test identity.
        # Child records must be handled by provider cascades; failed cleanup is a release blocker.
        try:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute('DELETE FROM neon_auth."user" WHERE email = %s', (email,))
                    cur.execute("DELETE FROM public.obrasignal_auth_invites WHERE id = %s", (invited_id,))
            print("SYNTHETIC_CLEANUP_PASS")
        except Exception:
            print("SYNTHETIC_CLEANUP_FAILURE_MANUAL_REVIEW_REQUIRED")
            raise
        finally:
            conn.close()

if __name__ == "__main__":
    sys.exit(main())
