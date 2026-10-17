"""Neon issuer compatibility using cryptographically signed synthetic tokens.

This test does NOT imply a Neon-issued token has been observed in production.
"""
import json
import time
import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519
from auth_context_jwt import JwtVerifier

NEON_ISSUER="https://ep-crimson-wildflower-b9rztglz.neonauth.c-7.eu-central-1.aws.neon.tech"\nNEON_JWKS=NEON_ISSUER+"/obrasignal_auth/auth/.well-known/jwks.json"

def test_new_identity_provider_accepts_correctly_signed_neon_issuer(monkeypatch):
    key=ed25519.Ed25519PrivateKey.generate()
    jwk=json.loads(jwt.algorithms.OKPAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid":"synthetic-neon-key","use":"sig","alg":"EdDSA"})
    verifier=JwtVerifier(issuer=NEON_ISSUER,audience=NEON_ISSUER,jwks_url=NEON_JWKS)
    monkeypatch.setattr(verifier,"_key_for",lambda kid:jwk if kid=="synthetic-neon-key" else None)
    now=int(time.time())
    base={"sub":"synthetic-user","iss":NEON_ISSUER,"aud":NEON_ISSUER,"iat":now-5,"exp":now+3600}
    def token(claims):
        return jwt.encode(claims,key,algorithm="EdDSA",headers={"kid":"synthetic-neon-key"})
    assert verifier.verify(token(base)).subject=="synthetic-user"
    for field,wrong in [("iss","https://certactum.com"),("aud","not-obrasignal")]:
        altered=dict(base);altered[field]=wrong
        try: verifier.verify(token(altered))
        except jwt.InvalidTokenError: pass
        else: raise AssertionError(f"{field} tamper accepted")
