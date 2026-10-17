"""Neon issuer compatibility using cryptographically signed synthetic tokens.

This test does NOT imply a Neon-issued token has been observed in production.
"""
import json
import time
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from auth_context_jwt import JwtVerifier

NEON_ISSUER="https://ep-crimson-wildflower-b9rztglz.neonauth.c-7.eu-central-1.aws.neon.tech/obrasignal_auth/auth"

def test_new_identity_provider_accepts_correctly_signed_neon_issuer(monkeypatch):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid":"synthetic-neon-key","use":"sig","alg":"RS256"})
    verifier=JwtVerifier(issuer=NEON_ISSUER,audience="authenticated",jwks_url=NEON_ISSUER+"/.well-known/jwks.json")
    monkeypatch.setattr(verifier,"_key_for",lambda kid:jwk if kid=="synthetic-neon-key" else None)
    now=int(time.time())
    base={"sub":"synthetic-user","iss":NEON_ISSUER,"aud":"authenticated","iat":now-5,"exp":now+3600}
    def token(claims):
        return jwt.encode(claims,key,algorithm="RS256",headers={"kid":"synthetic-neon-key"})
    assert verifier.verify(token(base)).subject=="synthetic-user"
    for field,wrong in [("iss","https://certactum.com"),("aud","not-obrasignal")]:
        altered=dict(base);altered[field]=wrong
        try: verifier.verify(token(altered))
        except jwt.InvalidTokenError: pass
        else: raise AssertionError(f"{field} tamper accepted")
