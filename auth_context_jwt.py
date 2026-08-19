"""JWT verification boundary for production ObraSignal API requests."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from threading import Lock
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request as UrlRequest, urlopen

import jwt
from jwt import InvalidTokenError


@dataclass(frozen=True)
class JwtIdentity:
    account_id: str
    subject: str
    claims: dict


def _normalize_supabase_issuer(issuer: str) -> str:
    """Accept the common Supabase project URL and normalize it to the JWT issuer."""
    value = (issuer or "").strip().rstrip("/")
    if not value:
        return value
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc.endswith(".supabase.co"):
        path = parsed.path.rstrip("/")
        if not path:
            return urlunsplit((parsed.scheme, parsed.netloc, "/auth/v1", "", ""))
    return value


def _default_jwks_url(issuer: str) -> str:
    """Return the provider's public-key discovery URL."""
    return f"{issuer.rstrip('/')}/.well-known/jwks.json"


class JwtVerifier:
    def __init__(self, issuer: str, audience: str = "authenticated", jwks_url: str = "", cache_seconds: int = 300):
        if not issuer:
            raise RuntimeError("JWT provider issuer is not configured")
        self.issuer = _normalize_supabase_issuer(issuer)
        self.audience = (audience or "authenticated").strip()
        # Supabase's JWT issuer is https://<project>.supabase.co/auth/v1 and its
        # asymmetric signing keys are published at the corresponding discovery URL.
        # Keep an explicit override for other OIDC-compatible providers.
        self.jwks_url = (jwks_url or _default_jwks_url(self.issuer)).strip()
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
