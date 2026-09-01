from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from factory_cloud.assurance_kernel import EvidenceEnvelope
from vertical_apps.industrial_claims.proof import canonical_json_bytes, sha256_hex


class SecureCaptureRegistryError(RuntimeError):
    pass


ROLE_SOURCE_TYPES = {
    "commercial_basis": "commercial_basis",
    "event": "industrial_commercial_event",
    "cost": "cost_evidence",
}


def _required(value: object, *, label: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise SecureCaptureRegistryError(f"invalid secure-capture {label}")
    return text


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise SecureCaptureRegistryError(f"invalid secure-capture {label}")
    return text


def _aware(value: object, *, label: str) -> str:
    text = _required(value, label=label, maximum=128)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SecureCaptureRegistryError(f"invalid secure-capture {label}") from exc
    if parsed.tzinfo is None:
        raise SecureCaptureRegistryError(f"secure-capture {label} must include timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SecureCaptureRegistry:
    """Append-only registry of immutable-original evidence envelopes.

    Original bytes live only in the configured immutable object store. This DB
    records the exact EvidenceEnvelope metadata/hash needed to bind that original
    into a case later without re-uploading or pretending extracted text is the
    original document. A retry is idempotent only when the complete durable record
    is identical; any changed content/metadata under the same evidence_id fails.
    """

    def __init__(self, database: str | Path) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS causledger_secure_capture_envelopes(
                    evidence_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    evidence_role TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    metadata_sha256 TEXT NOT NULL,
                    original_receipt_ref TEXT NOT NULL,
                    captured_by TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_causledger_secure_capture_tenant
                    ON causledger_secure_capture_envelopes(tenant_id,evidence_role,recorded_at,evidence_id);
                CREATE TRIGGER IF NOT EXISTS causledger_secure_capture_no_update
                    BEFORE UPDATE ON causledger_secure_capture_envelopes
                    BEGIN SELECT RAISE(ABORT,'secure capture envelopes are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_secure_capture_no_delete
                    BEFORE DELETE ON causledger_secure_capture_envelopes
                    BEGIN SELECT RAISE(ABORT,'secure capture envelopes are append-only'); END;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _validated_record(
        *,
        evidence: EvidenceEnvelope,
        evidence_role: str,
        captured_by: str,
    ) -> dict[str, str]:
        role = str(evidence_role or "").strip().lower()
        expected_source = ROLE_SOURCE_TYPES.get(role)
        if expected_source is None:
            raise SecureCaptureRegistryError("secure-capture evidence role is unsupported")
        evidence_id = _required(evidence.evidence_id, label="evidence_id")
        tenant = _required(evidence.tenant_id, label="tenant_id", maximum=64)
        source_type = _required(evidence.source_type, label="source_type", maximum=128)
        source_ref = _required(evidence.source_ref, label="source_ref")
        if source_type != expected_source:
            raise SecureCaptureRegistryError("secure-capture source type does not match evidence role")
        received_at = _aware(evidence.received_at, label="received_at")
        content_hash = _sha256(evidence.content_hash, label="content_hash")
        actor = _required(captured_by, label="captured_by", maximum=256)
        metadata = dict(evidence.metadata or {})
        if str(metadata.get("capture_mode") or "") != "DIRECT_SECURE_ORIGINAL_CAPTURE":
            raise SecureCaptureRegistryError("secure-capture envelope is not direct original capture")
        if str(metadata.get("raw_content_persisted") or "").strip().lower() != "true":
            raise SecureCaptureRegistryError("secure-capture original bytes are not declared persisted")
        original_receipt_ref = _required(
            metadata.get("original_provider_receipt_ref"),
            label="original_provider_receipt_ref",
        )
        metadata_json = canonical_json_bytes(metadata).decode("utf-8")
        return {
            "evidence_id": evidence_id,
            "tenant_id": tenant,
            "evidence_role": role,
            "source_type": source_type,
            "source_ref": source_ref,
            "received_at": received_at,
            "content_hash": content_hash,
            "metadata_json": metadata_json,
            "metadata_sha256": sha256_hex(metadata_json.encode("utf-8")),
            "original_receipt_ref": original_receipt_ref,
            "captured_by": actor,
        }

    @staticmethod
    def _row_payload(row: sqlite3.Row) -> dict[str, str]:
        return {
            "evidence_id": str(row["evidence_id"]),
            "tenant_id": str(row["tenant_id"]),
            "evidence_role": str(row["evidence_role"]),
            "source_type": str(row["source_type"]),
            "source_ref": str(row["source_ref"]),
            "received_at": str(row["received_at"]),
            "content_hash": str(row["content_hash"]),
            "metadata_json": str(row["metadata_json"]),
            "metadata_sha256": str(row["metadata_sha256"]),
            "original_receipt_ref": str(row["original_receipt_ref"]),
            "captured_by": str(row["captured_by"]),
        }

    @classmethod
    def _envelope_from_row(cls, row: sqlite3.Row) -> EvidenceEnvelope:
        payload = cls._row_payload(row)
        if sha256_hex(payload["metadata_json"].encode("utf-8")) != payload["metadata_sha256"]:
            raise SecureCaptureRegistryError("secure-capture metadata hash mismatch")
        try:
            metadata = json.loads(payload["metadata_json"])
        except (TypeError, ValueError) as exc:
            raise SecureCaptureRegistryError("secure-capture metadata JSON is invalid") from exc
        if not isinstance(metadata, dict):
            raise SecureCaptureRegistryError("secure-capture metadata must be an object")
        if str(metadata.get("original_provider_receipt_ref") or "") != payload["original_receipt_ref"]:
            raise SecureCaptureRegistryError("secure-capture original receipt binding mismatch")
        if str(metadata.get("capture_mode") or "") != "DIRECT_SECURE_ORIGINAL_CAPTURE":
            raise SecureCaptureRegistryError("secure-capture mode binding mismatch")
        if str(metadata.get("raw_content_persisted") or "").strip().lower() != "true":
            raise SecureCaptureRegistryError("secure-capture original persistence binding mismatch")
        _sha256(payload["content_hash"], label="content_hash")
        _aware(payload["received_at"], label="received_at")
        expected_source = ROLE_SOURCE_TYPES.get(payload["evidence_role"])
        if expected_source != payload["source_type"]:
            raise SecureCaptureRegistryError("secure-capture role/source binding mismatch")
        return EvidenceEnvelope(
            evidence_id=payload["evidence_id"],
            tenant_id=payload["tenant_id"],
            source_type=payload["source_type"],
            source_ref=payload["source_ref"],
            received_at=payload["received_at"],
            content_hash=payload["content_hash"],
            metadata=metadata,
        )

    def record(
        self,
        *,
        evidence: EvidenceEnvelope,
        evidence_role: str,
        captured_by: str,
    ) -> EvidenceEnvelope:
        record = self._validated_record(
            evidence=evidence,
            evidence_role=evidence_role,
            captured_by=captured_by,
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM causledger_secure_capture_envelopes WHERE evidence_id=?",
                (record["evidence_id"],),
            ).fetchone()
            if existing is not None:
                existing_payload = self._row_payload(existing)
                if existing_payload != record:
                    raise SecureCaptureRegistryError("immutable secure-capture evidence_id collision")
                return self._envelope_from_row(existing)
            conn.execute(
                """INSERT INTO causledger_secure_capture_envelopes(
                    evidence_id,tenant_id,evidence_role,source_type,source_ref,received_at,content_hash,
                    metadata_json,metadata_sha256,original_receipt_ref,captured_by,recorded_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record["evidence_id"], record["tenant_id"], record["evidence_role"], record["source_type"],
                    record["source_ref"], record["received_at"], record["content_hash"], record["metadata_json"],
                    record["metadata_sha256"], record["original_receipt_ref"], record["captured_by"], _now(),
                ),
            )
            conn.commit()
        return evidence

    def get(
        self,
        *,
        tenant_id: str,
        evidence_id: str,
        evidence_role: str | None = None,
        source_ref: str | None = None,
    ) -> EvidenceEnvelope:
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        evidence_key = _required(evidence_id, label="evidence_id")
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM causledger_secure_capture_envelopes
                   WHERE tenant_id=? AND evidence_id=?""",
                (tenant, evidence_key),
            ).fetchone()
        if row is None:
            raise SecureCaptureRegistryError("tenant-scoped secure-capture envelope not found")
        if evidence_role is not None and str(row["evidence_role"]) != str(evidence_role).strip().lower():
            raise SecureCaptureRegistryError("secure-capture evidence role does not match request")
        if source_ref is not None and str(row["source_ref"]) != str(source_ref).strip():
            raise SecureCaptureRegistryError("secure-capture source reference does not match request")
        return self._envelope_from_row(row)

    def count(self, *, tenant_id: str) -> int:
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM causledger_secure_capture_envelopes WHERE tenant_id=?",
                (tenant,),
            ).fetchone()
        return int(row["n"])
