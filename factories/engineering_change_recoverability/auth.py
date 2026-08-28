from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time


class AuthError(ValueError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def require_secret() -> bytes:
    value = os.getenv("ECE_AUTH_SECRET", "").encode()
    if len(value) < 32:
        raise RuntimeError("ECE_AUTH_SECRET must be at least 32 bytes")
    return value


def issue_token(tenant_id: str, *, ttl_seconds: int = 3600, now: int | None = None, secret: bytes | None = None) -> str:
    tenant_id = str(tenant_id or "").strip()
    if not tenant_id:
        raise ValueError("tenant_id required")
    now = int(time.time() if now is None else now)
    payload = {"tenant_id": tenant_id, "iat": now, "exp": now + int(ttl_seconds)}
    body = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    key = secret or require_secret()
    sig = _b64(hmac.new(key, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str, *, now: int | None = None, secret: bytes | None = None) -> dict:
    try:
        body, supplied = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("malformed_token") from exc
    key = secret or require_secret()
    expected = _b64(hmac.new(key, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(supplied, expected):
        raise AuthError("invalid_signature")
    try:
        payload = json.loads(_unb64(body))
    except Exception as exc:
        raise AuthError("invalid_payload") from exc
    tenant_id = str(payload.get("tenant_id") or "").strip()
    if not tenant_id:
        raise AuthError("tenant_missing")
    current = int(time.time() if now is None else now)
    exp = int(payload.get("exp") or 0)
    iat = int(payload.get("iat") or 0)
    if iat > current + 60:
        raise AuthError("token_from_future")
    if exp <= current:
        raise AuthError("token_expired")
    return payload


def bearer_tenant(header: str | None, *, now: int | None = None, secret: bytes | None = None) -> str:
    raw = str(header or "").strip()
    if not raw.lower().startswith("bearer "):
        raise AuthError("bearer_token_required")
    return str(verify_token(raw[7:].strip(), now=now, secret=secret)["tenant_id"])
