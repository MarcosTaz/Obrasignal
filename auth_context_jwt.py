"""JWT verification boundary for production ObraSignal API requests."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from threading import Lock
from urllib.request import Request as UrlRequest, urlopen

import jwt
from jwt import InvalidTokenError


@dataclass(frozen=True)
class JwtIdentity:
    account_id: str
    subject: str
    claims: dict


class JwtVerifier:
    def __init__(self, issuer: str, audience: str = "authenticated", jwks_url: str = "", cache_seconds: int = 300):
        if not issuer:
            raise RuntimeError("JWT provider issuer is not configured")
        self.issuer = issuer.rstrip("/")
        self.audience = (audience or "authenticated").strip()
        # Supabase's canonical JWKS endpoint is derived directly from the JWT issuer.
        # Keep an explicit override for other OIDC-compatible providers.
        self.jwks_url = (jwks_url or f"{self.issuer}/.well-known/jwks.json").strip()
        self.cache_seconds = max(30, int(cache_seconds))
        self._keys = None
        self._expires_at = 0.0
        self._lock = Lock()

    def _jwks(self):
        now = time.time()
        if self._keys and now < self._expires_at:
            return self._keys
        with self._lock:
            now = time.time()
            if self._keys and now < self._expires_at:
                return self._keys
            req = UrlRequest(self.jwks_url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=10) as response:
                payload = json.load(response)
            keys = payload.get("keys") or []
            if not keys:
                raise RuntimeError("JWT JWKS returned no keys")
            self._keys = {str(item["kid"]): item for item in keys if item.get("kid")}
            self._expires_at = now + self.cache_seconds
            return self._keys

    def verify(self, token: str) -> JwtIdentity:
        if not token:
            raise InvalidTokenError("missing token")
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        alg = header.get("alg")
        # Production verification intentionally accepts only asymmetric Supabase/OIDC
        # signing algorithms. Legacy HS256 requires a private shared secret and is not
        # accepted by this public-key verifier.
        if not kid or alg not in {"RS256", "ES256"}:
            raise InvalidTokenError("unsupported JWT header")
        jwk = self._jwks().get(str(kid))
        if not jwk:
            raise InvalidTokenError("unknown JWT key id")
        key = jwt.PyJWK(jwk).key
        claims = jwt.decode(
            token,
            key=key,
            algorithms=[alg],
            issuer=self.issuer,
            audience=self.audience,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        subject = str(claims["sub"])
        return JwtIdentity(account_id=subject, subject=subject, claims=claims)


def production_verifier() -> JwtVerifier:
    issuer = os.getenv("OBRASIGNAL_JWT_ISSUER", "").strip()
    return JwtVerifier(
        issuer=issuer,
        audience=os.getenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated"),
        jwks_url=os.getenv("OBRASIGNAL_JWKS_URL", ""),
        cache_seconds=int(os.getenv("OBRASIGNAL_JWKS_CACHE_SECONDS", "300")),
    )
