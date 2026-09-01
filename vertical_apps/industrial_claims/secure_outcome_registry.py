from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from factory_cloud.assurance_kernel import EvidenceEnvelope
from vertical_apps.industrial_claims.outcome_authorization import (
    DOCUMENTED_FINAL_OUTCOME_PURPOSE,
    OutcomeAuthorizationError,
    recompute_outcome_authorization_scope_sha256,
)
from vertical_apps.industrial_claims.proof import canonical_json_bytes, sha256_hex


class SecureOutcomeRegistryError(RuntimeError):
    pass


def _required(value: object, *, label: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise SecureOutcomeRegistryError(f"invalid secure outcome {label}")
    return text


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise SecureOutcomeRegistryError(f"invalid secure outcome {label}")
    return text


def _aware(value: object, *, label: str) -> str:
    text = _required(value, label=label, maximum=128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SecureOutcomeRegistryError(f"invalid secure outcome {label}") from exc
    if parsed.tzinfo is None:
        raise SecureOutcomeRegistryError(f"secure outcome {label} must include timezone")
    return parsed.isoformat()


def _true(value: object) -> bool:
    return value is True or str(value or "").strip().lower() == "true"


def _validate_evidence(evidence: EvidenceEnvelope, *, captured_by: str) -> dict[str, str]:
    evidence_id = _required(evidence.evidence_id, label="evidence_id")
    tenant_id = _required(evidence.tenant_id, label="tenant_id", maximum=64)
    if not evidence_id.startswith(f"{tenant_id}:"):
        raise SecureOutcomeRegistryError("secure outcome evidence_id is outside tenant namespace")
    if _required(evidence.source_type, label="source_type", maximum=128) != "recovery_outcome_evidence":
        raise SecureOutcomeRegistryError("secure outcome source type is invalid")
    source_ref = _required(evidence.source_ref, label="source_ref")
    received_at = _aware(evidence.received_at, label="received_at")
    content_hash = _sha256(evidence.content_hash, label="content_hash")
    actor = _required(captured_by, label="captured_by", maximum=256)
    metadata = dict(evidence.metadata or {})
    if str(metadata.get("verification_state") or "").strip().upper() != "CONTENT_HASHED":
        raise SecureOutcomeRegistryError("secure outcome content-hash verification state is invalid")
    if str(metadata.get("capture_mode") or "") != "DIRECT_SECURE_ORIGINAL_CAPTURE":
        raise SecureOutcomeRegistryError("secure outcome is not direct original capture")
    if not _true(metadata.get("raw_content_persisted")):
        raise SecureOutcomeRegistryError("secure outcome original bytes are not durably persisted")
    if not _true(metadata.get("original_version_readback_verified")):
        raise SecureOutcomeRegistryError("secure outcome exact-version readback is not verified")
    if not _true(metadata.get("proof_integrity_sealed")):
        raise SecureOutcomeRegistryError("secure outcome integrity seal is not verified")
    if str(metadata.get("immutability") or "").strip().upper() != "WORM_LOCKED":
        raise SecureOutcomeRegistryError("secure outcome original is not WORM locked")
    if not _true(metadata.get("worm_lock_verified")):
        raise SecureOutcomeRegistryError("secure outcome WORM lock is not verified")
    if str(metadata.get("original_retention_mode") or "").strip().upper() != "COMPLIANCE":
        raise SecureOutcomeRegistryError("secure outcome original is not under COMPLIANCE retention")
    if str(metadata.get("outcome_purpose") or "").strip().upper() != DOCUMENTED_FINAL_OUTCOME_PURPOSE:
        raise SecureOutcomeRegistryError("secure outcome authorization purpose is invalid")
    authorization_id = _required(metadata.get("outcome_authorization_id"), label="authorization_id", maximum=256)
    scope_sha256 = _sha256(metadata.get("outcome_authorization_scope_sha256"), label="authorization_scope_sha256")
    finding_id = _required(metadata.get("outcome_finding_id"), label="finding_id", maximum=2048)
    if not finding_id.startswith(f"{tenant_id}:"):
        raise SecureOutcomeRegistryError("secure outcome finding_id is outside tenant namespace")
    authorized_at = _aware(metadata.get("outcome_authorized_at"), label="authorized_at")
    expires_at = _aware(metadata.get("outcome_authorization_expires_at"), label="authorization_expires_at")
    if datetime.fromisoformat(expires_at) < datetime.fromisoformat(authorized_at):
        raise SecureOutcomeRegistryError("secure outcome authorization chronology is invalid")
    received = datetime.fromisoformat(received_at)
    if received < datetime.fromisoformat(authorized_at) or received > datetime.fromisoformat(expires_at):
        raise SecureOutcomeRegistryError("secure outcome received_at is outside authorized outcome window")
    minimum_retention = _aware(metadata.get("outcome_minimum_immutable_retention_until"), label="minimum_immutable_retention_until")
    provider_retention = _aware(metadata.get("original_retention_until"), label="original_retention_until")
    if datetime.fromisoformat(provider_retention) < datetime.fromisoformat(minimum_retention):
        raise SecureOutcomeRegistryError("secure outcome provider retention is shorter than authorized retention")
    if not _true(metadata.get("outcome_immutable_retention_acknowledged")):
        raise SecureOutcomeRegistryError("secure outcome immutable retention was not authorized")
    _sha256(metadata.get("outcome_authorized_by_sha256"), label="authorized_by_sha256")
    _sha256(metadata.get("outcome_transfer_channel_sha256"), label="transfer_channel_sha256")
    sha512 = str(metadata.get("content_sha512") or "").strip().lower()
    if len(sha512) != 128 or any(ch not in "0123456789abcdef" for ch in sha512):
        raise SecureOutcomeRegistryError("secure outcome SHA-512 binding is invalid")
    original_receipt_ref = _required(metadata.get("original_provider_receipt_ref"), label="original_provider_receipt_ref")
    try:
        recomputed_scope_sha256 = recompute_outcome_authorization_scope_sha256(metadata, tenant_id=tenant_id)
    except OutcomeAuthorizationError as exc:
        raise SecureOutcomeRegistryError("secure outcome authorization scope cannot be recomputed") from exc
    if recomputed_scope_sha256 != scope_sha256:
        raise SecureOutcomeRegistryError("secure outcome authorization scope hash mismatch")
    metadata_json = canonical_json_bytes(metadata).decode("utf-8")
    return {
        "evidence_id": evidence_id,
        "tenant_id": tenant_id,
        "finding_id": finding_id,
        "source_ref": source_ref,
        "received_at": received_at,
        "content_hash": content_hash,
        "metadata_json": metadata_json,
        "metadata_sha256": sha256_hex(metadata_json.encode("utf-8")),
        "authorization_id": authorization_id,
        "authorization_scope_sha256": scope_sha256,
        "original_receipt_ref": original_receipt_ref,
        "captured_by": actor,
    }


class SecureOutcomeRegistry:
    """Append-only registry for final-outcome originals authorized for one finding."""

    def __init__(self, database: str | Path) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS causledger_secure_outcome_envelopes(
                    evidence_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    metadata_sha256 TEXT NOT NULL,
                    authorization_id TEXT NOT NULL,
                    authorization_scope_sha256 TEXT NOT NULL,
                    original_receipt_ref TEXT NOT NULL,
                    captured_by TEXT NOT NULL,
                    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_causledger_secure_outcome_tenant
                    ON causledger_secure_outcome_envelopes(tenant_id,finding_id,evidence_id);
                CREATE TRIGGER IF NOT EXISTS causledger_secure_outcome_no_update
                    BEFORE UPDATE ON causledger_secure_outcome_envelopes
                    BEGIN SELECT RAISE(ABORT,'secure outcome envelopes are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_secure_outcome_no_delete
                    BEFORE DELETE ON causledger_secure_outcome_envelopes
                    BEGIN SELECT RAISE(ABORT,'secure outcome envelopes are append-only'); END;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, *, evidence: EvidenceEnvelope, captured_by: str) -> None:
        payload = _validate_evidence(evidence, captured_by=captured_by)
        ordered = (
            payload["evidence_id"], payload["tenant_id"], payload["finding_id"], payload["source_ref"],
            payload["received_at"], payload["content_hash"], payload["metadata_json"], payload["metadata_sha256"],
            payload["authorization_id"], payload["authorization_scope_sha256"], payload["original_receipt_ref"], payload["captured_by"],
        )
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT evidence_id,tenant_id,finding_id,source_ref,received_at,content_hash,metadata_json,metadata_sha256,authorization_id,authorization_scope_sha256,original_receipt_ref,captured_by FROM causledger_secure_outcome_envelopes WHERE evidence_id=?",
                (payload["evidence_id"],),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != ordered:
                    raise SecureOutcomeRegistryError("immutable secure outcome evidence id collision")
                return
            conn.execute(
                "INSERT INTO causledger_secure_outcome_envelopes(evidence_id,tenant_id,finding_id,source_ref,received_at,content_hash,metadata_json,metadata_sha256,authorization_id,authorization_scope_sha256,original_receipt_ref,captured_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                ordered,
            )

    def get(self, *, tenant_id: str, evidence_id: str, finding_id: str, source_ref: str) -> EvidenceEnvelope:
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        evidence_key = _required(evidence_id, label="evidence_id")
        finding_key = _required(finding_id, label="finding_id", maximum=2048)
        source = _required(source_ref, label="source_ref")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM causledger_secure_outcome_envelopes WHERE tenant_id=? AND evidence_id=? AND finding_id=? AND source_ref=?",
                (tenant, evidence_key, finding_key, source),
            ).fetchone()
        if row is None:
            raise SecureOutcomeRegistryError("tenant/finding-scoped secure outcome evidence not found")
        metadata_json = str(row["metadata_json"])
        if sha256_hex(metadata_json.encode("utf-8")) != str(row["metadata_sha256"]):
            raise SecureOutcomeRegistryError("secure outcome metadata hash mismatch")
        try:
            metadata = json.loads(metadata_json)
        except (TypeError, ValueError) as exc:
            raise SecureOutcomeRegistryError("secure outcome metadata JSON is invalid") from exc
        if not isinstance(metadata, dict):
            raise SecureOutcomeRegistryError("secure outcome metadata must be an object")
        evidence = EvidenceEnvelope(
            evidence_id=str(row["evidence_id"]), tenant_id=str(row["tenant_id"]), source_type="recovery_outcome_evidence",
            source_ref=str(row["source_ref"]), received_at=str(row["received_at"]), content_hash=str(row["content_hash"]), metadata=metadata,
        )
        canonical = _validate_evidence(evidence, captured_by=str(row["captured_by"]))
        if canonical["authorization_id"] != str(row["authorization_id"]):
            raise SecureOutcomeRegistryError("secure outcome authorization id binding mismatch")
        if canonical["authorization_scope_sha256"] != str(row["authorization_scope_sha256"]):
            raise SecureOutcomeRegistryError("secure outcome authorization scope binding mismatch")
        if canonical["original_receipt_ref"] != str(row["original_receipt_ref"]):
            raise SecureOutcomeRegistryError("secure outcome original receipt binding mismatch")
        return evidence