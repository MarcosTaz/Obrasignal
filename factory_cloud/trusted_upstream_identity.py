from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Callable

from factory_cloud.shared_contracts import SharedContractError

SECRET_ENV = "ASSISTED_UPSTREAM_HMAC_KEY"
MAX_IDENTITY_LENGTH = 256
DEFAULT_MAX_AGE_SECONDS = 120


@dataclass(frozen=True)
class VerifiedUpstreamIdentity:
    tenant_id: str
    actor_id: str


class TrustedUpstreamVerifier:
    """Verify identity injected by a trusted reverse proxy/internal gateway.

    The browser never receives the HMAC key and therefore cannot select or sign a
    tenant/actor identity. Signatures are bound to method + path + optional support
    role + timestamp, limiting replay and preventing role-header escalation.
    """

    def __init__(self, secret: str | bytes, *, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS, clock: Callable[[], float] = time.time):
        key = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
        if len(key) < 32:
            raise SharedContractError("trusted upstream HMAC key must be at least 32 bytes")
        if not 1 <= int(max_age_seconds) <= 900:
            raise SharedContractError("trusted upstream max age must be between 1 and 900 seconds")
        self._key = key
        self._max_age = int(max_age_seconds)
        self._clock = clock

    @classmethod
    def from_env(cls) -> "TrustedUpstreamVerifier":
        secret = os.environ.get(SECRET_ENV, "")
        if not secret:
            raise SharedContractError("trusted upstream identity verifier is not configured")
        return cls(secret)

    @staticmethod
    def _identity_value(value: str, label: str, *, required: bool = True) -> str:
        normalized = str(value or "").strip()
        if not normalized and not required:
            return ""
        if not normalized or len(normalized) > MAX_IDENTITY_LENGTH or any(ch in normalized for ch in "\r\n\x00"):
            raise SharedContractError(f"invalid trusted upstream {label}")
        return normalized

    @staticmethod
    def canonical_message(
        *, timestamp: int, method: str, path: str, tenant_id: str, actor_id: str,
        support_role: str = "",
    ) -> bytes:
        return f"v1\n{timestamp}\n{method.upper()}\n{path}\n{tenant_id}\n{actor_id}\n{support_role}".encode("utf-8")

    def sign(
        self, *, timestamp: int, method: str, path: str, tenant_id: str, actor_id: str,
        support_role: str = "",
    ) -> str:
        message = self.canonical_message(
            timestamp=timestamp, method=method, path=path,
            tenant_id=tenant_id, actor_id=actor_id, support_role=support_role,
        )
        return "v1=" + hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def verify_request(self, request) -> VerifiedUpstreamIdentity:
        tenant_id = self._identity_value(request.headers.get("X-Tenant-ID", ""), "tenant id")
        actor_id = self._identity_value(request.headers.get("X-Actor-ID", ""), "actor id")
        support_role = self._identity_value(
            request.headers.get("X-Support-Role", ""), "support role", required=False,
        )
        raw_timestamp = str(request.headers.get("X-Upstream-Timestamp", "")).strip()
        signature = str(request.headers.get("X-Upstream-Signature", "")).strip().lower()
        try:
            timestamp = int(raw_timestamp)
        except (TypeError, ValueError) as exc:
            raise SharedContractError("invalid trusted upstream timestamp") from exc
        now = int(self._clock())
        if abs(now - timestamp) > self._max_age:
            raise SharedContractError("trusted upstream identity signature expired")
        expected = self.sign(
            timestamp=timestamp, method=request.method, path=request.path,
            tenant_id=tenant_id, actor_id=actor_id, support_role=support_role,
        )
        if not signature or not hmac.compare_digest(signature, expected):
            raise SharedContractError("invalid trusted upstream identity signature")
        return VerifiedUpstreamIdentity(tenant_id=tenant_id, actor_id=actor_id)


def signed_test_headers(
    *, secret: str, tenant_id: str, actor_id: str, method: str, path: str, timestamp: int,
    support_role: str = "",
) -> dict[str, str]:
    """Deterministic helper for tests and synthetic-company harnesses only."""
    verifier = TrustedUpstreamVerifier(secret, clock=lambda: float(timestamp))
    headers = {
        "X-Tenant-ID": tenant_id,
        "X-Actor-ID": actor_id,
        "X-Upstream-Timestamp": str(timestamp),
        "X-Upstream-Signature": verifier.sign(
            timestamp=timestamp, method=method, path=path,
            tenant_id=tenant_id, actor_id=actor_id, support_role=support_role,
        ),
    }
    if support_role:
        headers["X-Support-Role"] = support_role
    return headers
