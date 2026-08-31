from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

from authz import CredentialRegistry


@dataclass(frozen=True)
class ProductionConfig:
    db_path: str
    audit_secret: bytes
    backup_key: bytes
    credentials: CredentialRegistry
    max_body_bytes: int


def _secret(name: str) -> bytes:
    value = os.getenv(name, "").encode()
    if len(value) < 32:
        raise RuntimeError(f"{name} must be at least 32 bytes")
    return value


def derive_backup_key(secret: bytes) -> bytes:
    if len(secret) < 32:
        raise ValueError("backup secret must be at least 32 bytes")
    return hashlib.sha256(secret).digest()


def _credentials() -> CredentialRegistry:
    raw = os.getenv("ROYALTYRECOVER_CREDENTIALS_JSON", "").strip()
    if not raw:
        raise RuntimeError("ROYALTYRECOVER_CREDENTIALS_JSON is required in production")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ROYALTYRECOVER_CREDENTIALS_JSON must be valid JSON") from exc
    registry = CredentialRegistry.from_config(payload)
    if not registry.configured:
        raise RuntimeError("at least one credential is required")
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, list):
        raise RuntimeError("production credentials require modern keys array")
    seen_secrets = set()
    for item in keys:
        secret = str((item or {}).get("secret") or "")
        if len(secret.encode()) < 32:
            raise RuntimeError("production API credential secrets must be at least 32 bytes")
        if secret in seen_secrets:
            raise RuntimeError("production API credential secrets must be unique")
        seen_secrets.add(secret)
    return registry


def load_production_config() -> ProductionConfig:
    if (os.getenv("ROYALTYRECOVER_ENV") or "development").strip().lower() != "production":
        raise RuntimeError("ROYALTYRECOVER_ENV must be production")
    db_path = (os.getenv("ROYALTYRECOVER_DB_PATH") or "").strip()
    if not db_path or db_path == ":memory:":
        raise RuntimeError("ROYALTYRECOVER_DB_PATH must be a persistent production path")
    max_body_bytes = int(os.getenv("ROYALTYRECOVER_MAX_BODY_BYTES", "1048576"))
    if max_body_bytes < 1024 or max_body_bytes > 10 * 1024 * 1024:
        raise RuntimeError("ROYALTYRECOVER_MAX_BODY_BYTES must be between 1024 and 10485760")
    return ProductionConfig(
        db_path=db_path,
        audit_secret=_secret("ROYALTYRECOVER_AUDIT_SECRET"),
        backup_key=derive_backup_key(_secret("ROYALTYRECOVER_BACKUP_SECRET")),
        credentials=_credentials(),
        max_body_bytes=max_body_bytes,
    )


def readiness_snapshot(repo) -> dict:
    reasons = []
    try:
        load_production_config()
    except (RuntimeError, ValueError) as exc:
        reasons.append(str(exc))
    if not getattr(repo, "integrity_check", lambda: False)():
        reasons.append("database_integrity_failed")
    if not getattr(repo, "verify_audit_chain", lambda: False)():
        reasons.append("audit_chain_failed")
    return {
        "ready": not reasons,
        "environment": (os.getenv("ROYALTYRECOVER_ENV") or "development").strip().lower(),
        "reasons": reasons,
    }
