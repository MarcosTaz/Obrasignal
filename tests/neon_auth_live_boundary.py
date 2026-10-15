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
print("ANONYMOUS_SIGNUP_HTTP_STATUS",status)
if 200 <= status < 300:
    raise SystemExit("SECURITY_FAILURE: unauthorised signup API returned success")
if status in (400,401,403,409,422):
    print("ANONYMOUS_SIGNUP_REJECTED")
else:
    raise SystemExit("INCONCLUSIVE: API response is not an expected authorization rejection")

# Production read-only check is performed separately against the identity table.
