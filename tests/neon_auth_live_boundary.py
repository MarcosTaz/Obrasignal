"""Neon Auth live denial probe, synthetic identities only, no real mail or payments."""
import json
import sys
import urllib.error
import urllib.request
from uuid import uuid4

BASE="https://ep-crimson-wildflower-b9rztglz.neonauth.c-7.eu-central-1.aws.neon.tech/obrasignal_auth/auth"
email=f"no-invite-{uuid4().hex}@example.com"
payload={"name":"Unauthorized Synthetic", "email":email,"password":"LongUnsharedSynthetic2026!Aa"}
req=urllib.request.Request(BASE+"/sign-up/email",data=json.dumps(payload).encode(),method="POST",headers={"Content-Type":"application/json","Origin":"https://obrasignal.com"})
try:
    with urllib.request.urlopen(req,timeout=25) as resp:
        status=resp.status
        body=resp.read(1024)
except urllib.error.HTTPError as exc:
    status=exc.code
    body=exc.read(1024)
except (urllib.error.URLError,TimeoutError) as exc:
    print("NEON_AUTH_UNREACHABLE; test inconclusive")
    raise SystemExit(2)
try:
    parsed=json.loads(body.decode("utf-8"))
except (ValueError,UnicodeDecodeError):
    parsed={}
error_text=" ".join(str(parsed.get(k) or "") for k in ("code","message","error")).lower() if isinstance(parsed,dict) else ""
reason="INVITE_GATE" if "invitation" in error_text else "UPSTREAM_VALIDATION_OR_UNKNOWN"
print("ANONYMOUS_SIGNUP_REJECTION_CLASS",reason)
if isinstance(parsed,dict):
    code=str(parsed.get("code") or "").strip()
    if code and len(code)<=64 and all(ch.isupper() or ch.isdigit() or ch in "_-" for ch in code):
        print("ANONYMOUS_SIGNUP_PROVIDER_CODE",code)

print("ANONYMOUS_SIGNUP_HTTP_STATUS",status)
if 200 <= status < 300:
    raise SystemExit("SECURITY_FAILURE: unauthorised signup API returned success")
if status != 422 or not isinstance(parsed, dict) or parsed.get("code") != "FAILED_TO_CREATE_USER":
    raise SystemExit("INCONCLUSIVE: Neon provider did not return expected identity-creation denial")
print("ANONYMOUS_SIGNUP_REJECTED_AT_IDENTITY_CREATION")

# Production read-only check is performed separately against the identity table.
