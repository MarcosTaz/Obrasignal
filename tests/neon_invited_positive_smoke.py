"""Private invitation-only Better Auth E2E. Requires protected synthetic env inputs.
Never logs credentials or tokens. No customer mail or payment.
"""
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://ep-crimson-wildflower-b9rztglz.neonauth.c-7.eu-central-1.aws.neon.tech/obrasignal_auth/auth"
cookies = http.cookiejar.CookieJar()
http = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

def call(path, payload=None, method=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=body,
        method=method or ("POST" if body is not None else "GET"),
        headers={"Accept":"application/json","Content-Type":"application/json",
                 "Origin":"https://obrasignal.com"},
    )
    try:
        with http.open(req, timeout=25) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, {}

def main():
    email = os.environ.get("OS_TEST_EMAIL", "").strip().lower()
    invitation = os.environ.get("OS_TEST_INVITE", "")
    password = os.environ.get("OS_TEST_PASSWORD", "")
    if not (email.endswith("@example.com") and len(invitation) == 51
            and invitation.startswith("OS-") and len(password) >= 12):
        print("PRIVATE_SYNTHETIC_INPUTS_UNAVAILABLE")
        return 2
    code, signup = call("/sign-up/email", {"name":invitation + "|Synthetic ObraSignal",
        "email":email, "password":password})
    if not 200 <= code < 300:
        print("INVITED_SIGNUP_NOT_PROVEN", code)
        return 1
    print("INVITED_SIGNUP_ACCEPTED")
    # Fresh login proof: avoid relying solely on automatic signup session.
    cookies.clear()
    code, signin = call("/sign-in/email", {"email":email,"password":password})
    if not 200 <= code < 300:
        print("SIGNIN_NOT_PROVEN", code)
        return 1
    print("SIGNIN_ACCEPTED")
    code, session = call("/get-session")
    user = session.get("user", {}) if isinstance(session, dict) else {}
    if code != 200 or user.get("email", "").lower() != email:
        print("SESSION_IDENTITY_NOT_PROVEN", code)
        return 1
    print("SESSION_IDENTITY_VERIFIED")
    # A valid session must not allow guessing another password.
    cookies.clear()
    code, _ = call("/sign-in/email", {"email":email,"password":password + "-wrong"})
    if 200 <= code < 300:
        print("WRONG_PASSWORD_ACCEPTED")
        return 1
    print("WRONG_PASSWORD_REJECTED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
