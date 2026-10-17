"""Read-only public JWKS readiness proof for isolated ObraSignal Neon Auth."""
import json, urllib.request
URL="https://ep-crimson-wildflower-b9rztglz.neonauth.c-7.eu-central-1.aws.neon.tech/obrasignal_auth/auth/.well-known/jwks.json"
request=urllib.request.Request(URL,headers={"Accept":"application/json"})
with urllib.request.urlopen(request,timeout=20) as result:
    if result.status!=200:
        raise SystemExit("NEON_JWKS_NOT_AVAILABLE")
    content=result.read(1024*128)
payload=json.loads(content)
keys=payload.get("keys",[]) if isinstance(payload,dict) else []
if not isinstance(keys,list) or not keys:
    raise SystemExit("NEON_JWKS_NO_SIGNING_KEYS")
usable=[x for x in keys if isinstance(x,dict) and x.get("kid") and x.get("kty") in {"RSA","EC","OKP"} and x.get("use","sig")=="sig"]
if not usable:
    raise SystemExit("NEON_JWKS_NO_USABLE_PUBLIC_KEYS")
print("NEON_JWKS_PUBLIC_READY",len(usable))
