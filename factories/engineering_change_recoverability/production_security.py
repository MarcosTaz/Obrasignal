from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionConfig:
    environment: str
    auth_secret: bytes
    audit_secret: bytes
    backup_key: bytes
    max_body_bytes: int


def _secret(name: str) -> bytes:
    value = os.getenv(name, "").encode()
    if len(value) < 32:
        raise RuntimeError(f"{name} must be at least 32 bytes")
    return value


def derive_aes256_key(secret: bytes) -> bytes:
    if len(secret) < 32:
        raise ValueError("backup secret must be at least 32 bytes")
    return hashlib.sha256(secret).digest()


def load_production_config() -> ProductionConfig:
    environment = (os.getenv("ECE_ENV") or "development").strip().lower()
    max_body_bytes = int(os.getenv("ECE_MAX_BODY_BYTES", "1048576"))
    if max_body_bytes < 1024 or max_body_bytes > 10 * 1024 * 1024:
        raise RuntimeError("ECE_MAX_BODY_BYTES must be between 1024 and 10485760")
    if environment != "production":
        raise RuntimeError("ECE_ENV must be production")
    return ProductionConfig(
        environment=environment,
        auth_secret=_secret("ECE_AUTH_SECRET"),
        audit_secret=_secret("ECE_AUDIT_SECRET"),
        backup_key=derive_aes256_key(_secret("ECE_BACKUP_SECRET")),
        max_body_bytes=max_body_bytes,
    )


def backup_key_from_env() -> bytes:
    return derive_aes256_key(_secret("ECE_BACKUP_SECRET"))


def readiness_snapshot(store) -> dict:
    reasons: list[str] = []
    try:
        config = load_production_config()
    except (RuntimeError, ValueError) as exc:
        return {"ready": False, "environment": (os.getenv("ECE_ENV") or "development"), "reasons": [str(exc)]}
    if not store.integrity_check():
        reasons.append("database_integrity_failed")
    if not store.audit_enabled:
        reasons.append("audit_secret_not_loaded")
    elif not store.verify_audit_chain():
        reasons.append("audit_chain_failed")
    return {
        "ready": not reasons,
        "environment": config.environment,
        "audit_enabled": store.audit_enabled,
        "database_integrity": not any(r == "database_integrity_failed" for r in reasons),
        "reasons": reasons,
    }
