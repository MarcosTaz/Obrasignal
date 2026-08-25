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


def _is_native_supabase_url(value: str) -> bool:
    parsed = urlsplit((value or "").strip())
    hostname = (parsed.hostname or "").lower()
    return (
        parsed.scheme in {"http", "https"}
        and bool(hostname)
        and hostname.endswith(".supabase.co")
        and parsed.username is None
        and parsed.password is None
    )


def _normalize_supabase_issuer(issuer: str) -> str:
    """Canonicalize any native Supabase project URL to its JWT issuer.

    Render/client configuration has historically used either the project root,
    ``/rest/v1`` or ``/auth/v1``. All of those refer to the same Supabase
    project, while JWT ``iss`` is always the canonical ``/auth/v1`` URL.
    Canonicalizing the path prevents a valid token from being rejected solely
    because an equivalent project URL was configured.
    """
    value = (issuer or "").strip().rstrip("/")
    if not value:
        return value
    if _is_native_supabase_url(value):
        parsed = urlsplit(value)
        return urlunsplit((parsed.scheme, parsed.netloc, "/auth/v1", "", ""))
    return value


def _default_jwks_url(issuer: str) -> str:
    """Return the provider's public-key discovery URL."""
    return f"{issuer.rstrip('/')}/.well-known/jwks.json"


def _effective_jwks_url(issuer: str, override: str = "") -> str:
    """Resolve the JWKS endpoint without allowing stale Supabase overrides.

    Native Supabase issuers have one canonical public JWKS endpoint. An
    operator-provided ``OBRASIGNAL_JWKS_URL`` for the same provider can become
    stale across key migrations and previously caused otherwise-valid tokens to
    fail closed as unknown keys. For native Supabase projects the canonical
    issuer-derived endpoint is therefore authoritative. Explicit overrides are
    still supported for non-Supabase OIDC-compatible providers.
    """
    if _is_native_supabase_url(issuer):
        return _default_jwks_url(issuer)
    return (override or _default_jwks_url(issuer)).strip()


class JwtVerifier:
    def __init__(
        self,
        issuer: str,
        audience: str = "authenticated",
        jwks_url: str = "",
        cache_seconds: int = 300,
        stale_max_seconds: int = 3600,
        bootstrap_json: str = "",
    ):
        if not issuer:
            raise RuntimeError("JWT provider issuer is not configured")
        self.issuer = _normalize_supabase_issuer(issuer)
        self.audience = (audience or "authenticated").strip()
        # Supabase's JWT issuer is https://<project>.supabase.co/auth/v1 and its
        # asymmetric signing keys are published at the corresponding discovery
        # URL. Native Supabase always uses that canonical endpoint; an explicit
        # override remains available for other OIDC-compatible providers.
        self.jwks_url = _effective_jwks_url(self.issuer, jwks_url)
        self.cache_seconds = max(30, int(cache_seconds))
        self.stale_max_seconds = max(0, int(stale_max_seconds))
        self._keys = None
        self._expires_at = 0.0
        self._fetched_at = 0.0
        self._retry_at = 0.0
        self._generation = 0
        self._lock = Lock()
        self._keys_source = None
        self._provider_degraded = False
        if bootstrap_json:
            try:
                payload = json.loads(bootstrap_json)
                self._keys = self._validated_keys(payload)
            except (TypeError, ValueError, KeyError, jwt.PyJWTError) as exc:
                raise RuntimeError("OBRASIGNAL_JWKS_BOOTSTRAP_JSON is not a valid public JWKS") from exc
            self._fetched_at = time.time()
            self._expires_at = self._fetched_at + self.cache_seconds
            self._keys_source = "bootstrap"

    @staticmethod
    def _validated_keys(payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list) or not payload["keys"]:
            raise ValueError("JWKS must contain a non-empty keys list")
        keys = {}
        private_fields = {"d", "p", "q", "dp", "dq", "qi", "oth", "k"}
        for item in payload["keys"]:
            if not isinstance(item, dict) or not item.get("kid"):
                raise ValueError("each JWK must have a kid")
            if private_fields.intersection(item) or item.get("kty") not in {"RSA", "EC"}:
                raise ValueError("bootstrap JWKs must be asymmetric public keys")
            if item.get("alg") and item["alg"] not in {"RS256", "ES256"}:
                raise ValueError("bootstrap JWK uses an unsupported algorithm")
            jwt.PyJWK(item)
            kid = str(item["kid"])
            if kid in keys:
                raise ValueError("duplicate JWK kid")
            keys[kid] = item
        return keys

    def _fetch_jwks(self):
        req = UrlRequest(self.jwks_url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as response:
            payload = json.load(response)
        return self._validated_keys(payload)

    def provider_status(self) -> str:
        """Return a secret-free summary of the verifier's last known readiness."""
        with self._lock:
            if self._provider_degraded:
                return "degraded"
            if self._keys:
                return "ready"
            return "uninitialized"

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
                self._provider_degraded = True
                self._retry_at = time.time() + min(30, self.cache_seconds)
                if kid in keys and time.time() - self._fetched_at <= self.stale_max_seconds:
                    return keys[kid]
                raise JwksUnavailableError("JWT signing keys are temporarily unavailable") from exc

            self._keys = refreshed
            self._fetched_at = time.time()
            self._expires_at = self._fetched_at + self.cache_seconds
            self._retry_at = 0.0
            self._generation += 1
            self._keys_source = "remote"
            self._provider_degraded = False
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
        if jwk.get("alg") and jwk["alg"] != alg:
            raise InvalidTokenError("JWT algorithm does not match signing key")
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
        os.getenv("OBRASIGNAL_JWKS_BOOTSTRAP_JSON", ""),
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
                bootstrap_json=config[5],
            )
            _verifier_config = config
        return _verifier


def authentication_health() -> dict:
    """Return public-safe authentication configuration/readiness metadata.

    This is intentionally passive: health never calls the identity provider. A
    provider is ``ready`` only after the verifier has usable public keys,
    ``degraded`` after a failed JWKS refresh, and ``uninitialized`` before the
    first verification attempt. No issuer, JWKS URL, key material or secret is
    returned.
    """
    mode = (os.getenv("OBRASIGNAL_AUTH_MODE") or "development").strip().lower()
    if mode == "development":
        return {
            "mode": "development",
            "config_present": True,
            "provider_status": "not_applicable",
        }
    if mode != "provider":
        return {
            "mode": "invalid",
            "config_present": False,
            "provider_status": "misconfigured",
        }

    issuer = os.getenv("OBRASIGNAL_JWT_ISSUER", "").strip()
    audience = os.getenv("OBRASIGNAL_JWT_AUDIENCE", "authenticated").strip()
    config_present = bool(issuer and audience)
    if not config_present:
        return {
            "mode": "provider",
            "config_present": False,
            "provider_status": "misconfigured",
        }
    try:
        verifier = production_verifier()
    except (RuntimeError, TypeError, ValueError):
        return {
            "mode": "provider",
            "config_present": False,
            "provider_status": "misconfigured",
        }
    return {
        "mode": "provider",
        "config_present": True,
        "provider_status": verifier.provider_status(),
    }
