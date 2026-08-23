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


class JwksUnavailableError(Exception):
    """The signing-key service is unavailable and no cached key can verify the token."""


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
    def __init__(
        self,
        issuer: str,
        audience: str = "authenticated",
        jwks_url: str = "",
        cache_seconds: int = 300,
        stale_max_seconds: int = 3600,
    ):
        if not issuer:
            raise RuntimeError("JWT provider issuer is not configured")
        self.issuer = _normalize_supabase_issuer(issuer)
        self.audience = (audience or "authenticated").strip()
        # Supabase's JWT issuer is https://<project>.supabase.co/auth/v1 and its
        # asymmetric signing keys are published at the corresponding discovery URL.
        # Keep an explicit override for other OIDC-compatible providers.
        self.jwks_url = (jwks_url or _default_jwks_url(self.issuer)).strip()
        self.cache_seconds = max(30, int(cache_seconds))
        self.stale_max_seconds = max(0, int(stale_max_seconds))
        self._keys = None
        self._expires_at = 0.0
        self._fetched_at = 0.0
        self._retry_at = 0.0
        self._generation = 0
        self._lock = Lock()

    def _fetch_jwks(self):
        req = UrlRequest(self.jwks_url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as response:
            payload = json.load(response)
        keys = {str(item["kid"]): item for item in (payload.get("keys") or []) if item.get("kid")}
        if not keys:
            raise ValueError("JWT JWKS returned no keys")
        return keys

    def _key_for(self, kid: str):
        """Return a cached public JWK, refreshing once when stale or unknown.

        The generation check makes refresh single-flight: callers which waited for
        another refresh consume that result instead of fetching the same JWKS again.
        A short failure backoff provides the same protection while the origin is down.
        """
        now = time.time()
        keys = self._keys or {}
        generation = self._generation
        if kid in keys and now < self._expires_at:
            return keys[kid]

        with self._lock:
            now = time.time()
            keys = self._keys or {}
            if kid in keys and now < self._expires_at:
                return keys[kid]
            if self._generation != generation:
                if kid in keys:
                    return keys[kid]
                raise InvalidTokenError("unknown JWT key id")
            if now < self._retry_at:
                if kid in keys and now - self._fetched_at <= self.stale_max_seconds:
                    return keys[kid]
                raise JwksUnavailableError("JWT signing keys are temporarily unavailable")

            try:
                refreshed = self._fetch_jwks()
            except Exception as exc:
                # Never replace the last known-good public keys with a failed or
                # malformed response. Cached keys still perform full JWT validation.
                self._retry_at = time.time() + min(30, self.cache_seconds)
                if kid in keys and time.time() - self._fetched_at <= self.stale_max_seconds:
                    return keys[kid]
                raise JwksUnavailableError("JWT signing keys are temporarily unavailable") from exc

            self._keys = refreshed
            self._fetched_at = time.time()
            self._expires_at = self._fetched_at + self.cache_seconds
            self._retry_at = 0.0
            self._generation += 1
            if kid not in refreshed:
                raise InvalidTokenError("unknown JWT key id")
            return refreshed[kid]

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
        jwk = self._key_for(str(kid))
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


_verifier = None
_verifier_config = None
_verifier_lock = Lock()


def production_verifier() -> JwtVerifier:
    global _verifier, _verifier_config
    issuer = os.getenv("OBRASIGNAL_JWT_ISSUER", "").strip()
    config = (
        issuer,
        os.getenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated"),
        os.getenv("OBRASIGNAL_JWKS_URL", ""),
        int(os.getenv("OBRASIGNAL_JWKS_CACHE_SECONDS", "300")),
        int(os.getenv("OBRASIGNAL_JWKS_STALE_MAX_SECONDS", "3600")),
    )
    if _verifier is not None and _verifier_config == config:
        return _verifier
    with _verifier_lock:
        if _verifier is None or _verifier_config != config:
            _verifier = JwtVerifier(
                issuer=config[0],
                audience=config[1],
                jwks_url=config[2],
                cache_seconds=config[3],
                stale_max_seconds=config[4],
            )
            _verifier_config = config
        return _verifier
