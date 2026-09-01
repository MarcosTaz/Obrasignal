from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from vertical_apps.industrial_claims.proof import ExternalAttestation, canonical_json_bytes, sha256_hex


class ProofAttestationArchiveError(RuntimeError):
    pass


MAX_RECEIPT_BYTES = 1_048_576
EXPECTED_PURPOSE = "CAUSLEDGER_DURABLE_PROOF_TARGET"


def _required(value: object, *, label: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ProofAttestationArchiveError(f"invalid {label}")
    return text


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ProofAttestationArchiveError(f"invalid {label} SHA-256")
    return text


def _optional_iso(value: object) -> str | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProofAttestationArchiveError("invalid attestation issued_at") from exc
    if parsed.tzinfo is None:
        raise ProofAttestationArchiveError("attestation issued_at must include timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _external_attestation(value: Mapping[str, Any]) -> ExternalAttestation:
    if not isinstance(value, Mapping):
        raise ProofAttestationArchiveError("external attestation receipt must be an object")
    details = value.get("details") or {}
    if not isinstance(details, Mapping):
        raise ProofAttestationArchiveError("external attestation details must be an object")
    try:
        return ExternalAttestation(
            kind=str(value.get("kind") or ""),
            provider=str(value.get("provider") or ""),
            state=str(value.get("state") or ""),
            digest_algorithm=str(value.get("digest_algorithm") or ""),
            digest=str(value.get("digest") or ""),
            provider_ref=str(value.get("provider_ref")) if value.get("provider_ref") is not None else None,
            issued_at=str(value.get("issued_at")) if value.get("issued_at") is not None else None,
            validation_ref=str(value.get("validation_ref")) if value.get("validation_ref") is not None else None,
            details=dict(details),
        )
    except ValueError as exc:
        raise ProofAttestationArchiveError("external attestation receipt is invalid") from exc


class ProofAttestationArchive:
    """Append-only recovery archive for external proof receipts.

    The externalization audit ledger proves that an operation started/finished.
    This archive separately preserves the actual receipts needed to reconstruct
    that proof later. Each receipt is canonicalized, payload-hashed and linked in
    a tenant+target hash chain. Raw customer evidence bytes are never accepted.
    """

    def __init__(self, database: str | Path) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS causledger_external_attestation_receipts(
                    sequence INTEGER PRIMARY KEY,
                    receipt_id TEXT NOT NULL UNIQUE,
                    operation_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    subject_ref TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    state TEXT NOT NULL,
                    digest_algorithm TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    provider_ref TEXT,
                    issued_at TEXT,
                    validation_ref TEXT,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    previous_receipt_hash TEXT,
                    receipt_hash TEXT NOT NULL UNIQUE,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(operation_id,kind)
                );
                CREATE INDEX IF NOT EXISTS idx_causledger_external_attestation_subject
                    ON causledger_external_attestation_receipts(tenant_id,subject_ref,sequence);
                CREATE INDEX IF NOT EXISTS idx_causledger_external_attestation_operation
                    ON causledger_external_attestation_receipts(tenant_id,operation_id,sequence);
                CREATE TRIGGER IF NOT EXISTS causledger_external_attestation_no_update
                    BEFORE UPDATE ON causledger_external_attestation_receipts
                    BEGIN SELECT RAISE(ABORT,'external attestation receipts are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_external_attestation_no_delete
                    BEFORE DELETE ON causledger_external_attestation_receipts
                    BEGIN SELECT RAISE(ABORT,'external attestation receipts are append-only'); END;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_body(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "sequence": int(row["sequence"]),
            "receipt_id": str(row["receipt_id"]),
            "operation_id": str(row["operation_id"]),
            "tenant_id": str(row["tenant_id"]),
            "subject_ref": str(row["subject_ref"]),
            "kind": str(row["kind"]),
            "provider": str(row["provider"]),
            "state": str(row["state"]),
            "digest_algorithm": str(row["digest_algorithm"]),
            "digest": str(row["digest"]),
            "provider_ref": row["provider_ref"],
            "issued_at": row["issued_at"],
            "validation_ref": row["validation_ref"],
            "payload_sha256": str(row["payload_sha256"]),
            "previous_receipt_hash": row["previous_receipt_hash"],
            "recorded_at": str(row["recorded_at"]),
        }

    def _subject_rows(self, conn: sqlite3.Connection, *, tenant_id: str, subject_ref: str) -> list[sqlite3.Row]:
        return list(conn.execute(
            """SELECT * FROM causledger_external_attestation_receipts
               WHERE tenant_id=? AND subject_ref=? ORDER BY sequence""",
            (tenant_id, subject_ref),
        ).fetchall())

    def _verify_rows(self, rows: Sequence[sqlite3.Row]) -> str | None:
        previous: str | None = None
        for index, row in enumerate(rows):
            try:
                payload = json.loads(str(row["payload_json"]))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ProofAttestationArchiveError(f"receipt {index} payload JSON is invalid") from exc
            if not isinstance(payload, dict):
                raise ProofAttestationArchiveError(f"receipt {index} payload is not an object")
            payload_bytes = canonical_json_bytes(payload)
            if len(payload_bytes) > MAX_RECEIPT_BYTES:
                raise ProofAttestationArchiveError(f"receipt {index} payload is too large")
            if sha256_hex(payload_bytes) != str(row["payload_sha256"]):
                raise ProofAttestationArchiveError(f"receipt {index} payload hash mismatch")
            attestation = _external_attestation(payload)
            if (
                attestation.kind != str(row["kind"])
                or attestation.provider != str(row["provider"])
                or attestation.state != str(row["state"])
                or attestation.digest_algorithm.upper() != str(row["digest_algorithm"]).upper()
                or attestation.digest.lower() != str(row["digest"]).lower()
                or attestation.provider_ref != row["provider_ref"]
                or _optional_iso(attestation.issued_at) != row["issued_at"]
                or attestation.validation_ref != row["validation_ref"]
            ):
                raise ProofAttestationArchiveError(f"receipt {index} row/payload binding mismatch")
            if row["previous_receipt_hash"] != previous:
                raise ProofAttestationArchiveError(f"receipt {index} previous-hash mismatch")
            body = self._row_body(row)
            expected = sha256_hex(body)
            if expected != str(row["receipt_hash"]):
                raise ProofAttestationArchiveError(f"receipt {index} chain hash mismatch")
            previous = expected
        return previous

    def archive_operation(
        self,
        *,
        operation_id: str,
        tenant_id: str,
        target_sha256: str,
        receipts: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        operation = _required(operation_id, label="operation_id", maximum=256)
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        target = _sha256(target_sha256, label="target")
        subject = f"causledger:proof-target:{target}"
        if not receipts:
            raise ProofAttestationArchiveError("at least one external attestation receipt is required")

        normalized: list[dict[str, Any]] = []
        seen_kinds: set[str] = set()
        for raw in receipts:
            attestation = _external_attestation(raw)
            if attestation.kind in seen_kinds:
                raise ProofAttestationArchiveError("duplicate attestation kind in one externalization operation")
            seen_kinds.add(attestation.kind)
            if attestation.digest_algorithm.upper() != "SHA-256" or attestation.digest.lower() != target:
                raise ProofAttestationArchiveError("external attestation is bound to another proof target")
            if str(attestation.details.get("subject_ref") or "").strip() != subject:
                raise ProofAttestationArchiveError("external attestation subject binding is missing or different")
            if str(attestation.details.get("purpose") or "").strip() != EXPECTED_PURPOSE:
                raise ProofAttestationArchiveError("external attestation purpose binding is missing or different")
            payload = attestation.as_dict()
            payload_bytes = canonical_json_bytes(payload)
            if len(payload_bytes) > MAX_RECEIPT_BYTES:
                raise ProofAttestationArchiveError("external attestation receipt exceeds archive size limit")
            normalized.append(payload)

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT COUNT(*) AS n FROM causledger_external_attestation_receipts WHERE operation_id=?",
                (operation,),
            ).fetchone()
            if int(existing["n"]) != 0:
                raise ProofAttestationArchiveError("externalization operation receipts are already archived")
            rows = self._subject_rows(conn, tenant_id=tenant, subject_ref=subject)
            previous = self._verify_rows(rows)
            receipt_ids: list[str] = []
            payloads: list[dict[str, Any]] = []
            for payload in normalized:
                sequence = int(conn.execute(
                    "SELECT COALESCE(MAX(sequence),0)+1 AS n FROM causledger_external_attestation_receipts"
                ).fetchone()["n"])
                kind = str(payload["kind"])
                receipt_id = f"{operation}:{kind}"
                payload_bytes = canonical_json_bytes(payload)
                payload_sha256 = sha256_hex(payload_bytes)
                issued_at = _optional_iso(payload.get("issued_at"))
                recorded_at = _now()
                body = {
                    "sequence": sequence,
                    "receipt_id": receipt_id,
                    "operation_id": operation,
                    "tenant_id": tenant,
                    "subject_ref": subject,
                    "kind": kind,
                    "provider": str(payload["provider"]),
                    "state": str(payload["state"]),
                    "digest_algorithm": str(payload["digest_algorithm"]).upper(),
                    "digest": str(payload["digest"]).lower(),
                    "provider_ref": payload.get("provider_ref"),
                    "issued_at": issued_at,
                    "validation_ref": payload.get("validation_ref"),
                    "payload_sha256": payload_sha256,
                    "previous_receipt_hash": previous,
                    "recorded_at": recorded_at,
                }
                receipt_hash = sha256_hex(body)
                conn.execute(
                    """INSERT INTO causledger_external_attestation_receipts(
                        sequence,receipt_id,operation_id,tenant_id,subject_ref,kind,provider,state,
                        digest_algorithm,digest,provider_ref,issued_at,validation_ref,payload_json,
                        payload_sha256,previous_receipt_hash,receipt_hash,recorded_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        sequence,receipt_id,operation,tenant,subject,kind,body["provider"],body["state"],
                        body["digest_algorithm"],body["digest"],body["provider_ref"],issued_at,
                        body["validation_ref"],payload_bytes.decode("utf-8"),payload_sha256,previous,
                        receipt_hash,recorded_at,
                    ),
                )
                previous = receipt_hash
                receipt_ids.append(receipt_id)
                payloads.append(payload)
            conn.commit()

        return {
            "operation_id": operation,
            "tenant_id": tenant,
            "subject_ref": subject,
            "target_sha256": target,
            "receipt_count": len(receipt_ids),
            "receipt_ids": receipt_ids,
            "receipts_sha256": sha256_hex(payloads),
            "archive_chain_head_sha256": previous,
            "append_only": True,
        }

    def operation_receipts(self, *, tenant_id: str, operation_id: str) -> dict[str, Any]:
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        operation = _required(operation_id, label="operation_id", maximum=256)
        with self._connect() as conn:
            rows = list(conn.execute(
                """SELECT * FROM causledger_external_attestation_receipts
                   WHERE tenant_id=? AND operation_id=? ORDER BY sequence""",
                (tenant, operation),
            ).fetchall())
            if not rows:
                raise ProofAttestationArchiveError("externalization operation receipts not found")
            subject = str(rows[0]["subject_ref"])
            subject_rows = self._subject_rows(conn, tenant_id=tenant, subject_ref=subject)
            chain_head = self._verify_rows(subject_rows)
        receipts = [json.loads(str(row["payload_json"])) for row in rows]
        return {
            "operation_id": operation,
            "tenant_id": tenant,
            "subject_ref": subject,
            "receipt_count": len(receipts),
            "receipts": receipts,
            "receipts_sha256": sha256_hex(receipts),
            "archive_chain_head_sha256": chain_head,
            "archive_chain_verified": True,
            "append_only": True,
        }
