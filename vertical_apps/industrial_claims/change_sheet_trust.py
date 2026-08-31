from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vertical_apps.industrial_claims.change_capture import ChangeCaptureStore
from vertical_apps.industrial_claims.proof import ExternalAttestation, canonical_json_bytes, sha256_hex
from vertical_apps.industrial_claims.proof_providers import ProofProvider, ProofRequest


class ChangeSheetTrustError(RuntimeError):
    pass


_VERIFIED_STATES = {"VERIFIED", "VALID"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required(value: object, *, label: str, max_chars: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_chars or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ChangeSheetTrustError(f"invalid {label}")
    return text


def _digest(value: object) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ChangeSheetTrustError("invalid change sheet SHA-256 digest")
    return text


class ChangeSheetTrustService:
    """Bind exact Change Capture Sheet bytes to independent time evidence.

    Timestamp requests carry the exact exported payload separately from metadata.
    The SHA-256 supplied to the evidence model must equal those bytes before any
    provider is called. This avoids both hash-of-hash ambiguity and races where a
    later factual edit could otherwise cause the token and exported file to differ.
    """

    def __init__(
        self,
        database: str | Path,
        *,
        capture_store: ChangeCaptureStore,
        qualified_timestamp_provider: ProofProvider,
    ) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.capture_store = capture_store
        self.provider = qualified_timestamp_provider
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS causledger_change_sheet_attestations(
                    attestation_id TEXT PRIMARY KEY,
                    attestation_hash TEXT NOT NULL UNIQUE,
                    tenant_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    sheet_id TEXT NOT NULL,
                    sheet_sha256 TEXT NOT NULL,
                    subject_ref TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    state TEXT NOT NULL,
                    digest_algorithm TEXT NOT NULL,
                    provider_ref TEXT,
                    issued_at TEXT,
                    validation_ref TEXT,
                    details_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_causledger_change_sheet_attestations_case
                    ON causledger_change_sheet_attestations(tenant_id,finding_id,recorded_at,attestation_id);
                CREATE INDEX IF NOT EXISTS idx_causledger_change_sheet_attestations_digest
                    ON causledger_change_sheet_attestations(tenant_id,finding_id,sheet_sha256,state);
                CREATE TRIGGER IF NOT EXISTS causledger_change_sheet_attestations_no_update
                    BEFORE UPDATE ON causledger_change_sheet_attestations
                    BEGIN SELECT RAISE(ABORT,'change sheet attestations are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_change_sheet_attestations_no_delete
                    BEFORE DELETE ON causledger_change_sheet_attestations
                    BEGIN SELECT RAISE(ABORT,'change sheet attestations are append-only'); END;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _subject_ref(sheet_id: str, digest: str) -> str:
        return f"causledger:change-sheet:{sheet_id}:{digest}"

    @staticmethod
    def _purpose() -> str:
        return "CHANGE_CAPTURE_SNAPSHOT_EXISTENCE_TIME"

    def _current_snapshot(self, *, tenant_id: str, finding_id: str) -> tuple[dict[str, Any], bytes, str, str]:
        status = self.capture_store.status(tenant_id=tenant_id, finding_id=finding_id)
        sheet, digest = self.capture_store.render_sheet(tenant_id=tenant_id, finding_id=finding_id)
        payload = sheet.encode("utf-8")
        digest = _digest(digest)
        if sha256_hex(payload) != digest:
            raise ChangeSheetTrustError("change sheet renderer digest does not match rendered bytes")
        return status, payload, digest, self._subject_ref(str(status["sheet_id"]), digest)

    def _validate_attestation(
        self,
        *,
        attestation: ExternalAttestation,
        expected_digest: str,
        expected_subject_ref: str,
    ) -> None:
        if attestation.kind != "QUALIFIED_TIMESTAMP":
            raise ChangeSheetTrustError("change sheet time provider returned the wrong attestation kind")
        if attestation.digest_algorithm.upper() != "SHA-256":
            raise ChangeSheetTrustError("change sheet time provider must bind SHA-256")
        if _digest(attestation.digest) != expected_digest:
            raise ChangeSheetTrustError("change sheet time receipt digest does not match snapshot")
        state = str(attestation.state or "").strip().upper()
        if state not in _VERIFIED_STATES:
            return
        details = dict(attestation.details or {})
        if str(details.get("subject_ref") or "").strip() != expected_subject_ref:
            raise ChangeSheetTrustError("verified change sheet timestamp is not bound to the exact snapshot subject")
        if str(details.get("purpose") or "").strip() != self._purpose():
            raise ChangeSheetTrustError("verified change sheet timestamp has the wrong proof purpose")
        if not str(attestation.provider_ref or "").strip():
            raise ChangeSheetTrustError("verified change sheet timestamp requires provider reference")
        if not str(attestation.issued_at or "").strip():
            raise ChangeSheetTrustError("verified change sheet timestamp requires independent issued_at")
        if not str(attestation.validation_ref or "").strip():
            raise ChangeSheetTrustError("verified change sheet timestamp requires validation material")

    def _row_attestation(self, row: sqlite3.Row) -> ExternalAttestation:
        try:
            details = json.loads(str(row["details_json"]))
        except (TypeError, ValueError) as exc:
            raise ChangeSheetTrustError("stored change sheet timestamp details are invalid") from exc
        if not isinstance(details, dict):
            raise ChangeSheetTrustError("stored change sheet timestamp details are invalid")
        digest = _digest(row["sheet_sha256"])
        sheet_id = _required(row["sheet_id"], label="sheet_id", max_chars=128)
        expected_subject = self._subject_ref(sheet_id, digest)
        if str(row["subject_ref"] or "").strip() != expected_subject:
            raise ChangeSheetTrustError("stored change sheet timestamp subject binding is invalid")
        try:
            attestation = ExternalAttestation(
                kind=str(row["kind"]), provider=str(row["provider"]), state=str(row["state"]),
                digest_algorithm=str(row["digest_algorithm"]), digest=digest,
                provider_ref=row["provider_ref"], issued_at=row["issued_at"],
                validation_ref=row["validation_ref"], details=details,
            )
        except ValueError as exc:
            raise ChangeSheetTrustError("stored change sheet timestamp envelope is invalid") from exc
        self._validate_attestation(attestation=attestation, expected_digest=digest, expected_subject_ref=expected_subject)
        body = {
            "tenant_id": str(row["tenant_id"]), "finding_id": str(row["finding_id"]),
            "sheet_id": sheet_id, "sheet_sha256": digest, "subject_ref": expected_subject,
            "attestation": attestation.as_dict(), "recorded_at": str(row["recorded_at"]),
        }
        expected_hash = sha256_hex(body)
        if str(row["attestation_hash"]) != expected_hash:
            raise ChangeSheetTrustError("stored change sheet timestamp receipt hash is invalid")
        if str(row["attestation_id"]) != f"sheettsa_{expected_hash[:24]}":
            raise ChangeSheetTrustError("stored change sheet timestamp receipt identity is invalid")
        return attestation

    def _existing_verified(self, *, tenant_id: str, finding_id: str, digest: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM causledger_change_sheet_attestations
                   WHERE tenant_id=? AND finding_id=? AND sheet_sha256=?
                     AND kind='QUALIFIED_TIMESTAMP' AND state IN ('VERIFIED','VALID')
                   ORDER BY recorded_at DESC,attestation_id DESC LIMIT 1""",
                (tenant_id, finding_id, digest),
            ).fetchone()
        if row is not None:
            self._row_attestation(row)
        return row

    @staticmethod
    def _public_attestation(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "attestation_id": str(row["attestation_id"]), "sheet_sha256": str(row["sheet_sha256"]),
            "kind": str(row["kind"]), "provider": str(row["provider"]), "state": str(row["state"]),
            "digest_algorithm": str(row["digest_algorithm"]), "provider_ref": row["provider_ref"],
            "issued_at": row["issued_at"], "validation_ref": row["validation_ref"],
            "recorded_at": str(row["recorded_at"]),
        }

    def attest_snapshot(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        sheet_id: str,
        payload: bytes,
        sheet_sha256: str,
        factual_window_closes_at: str,
    ) -> dict[str, Any]:
        tenant = _required(tenant_id, label="tenant_id", max_chars=64)
        finding = _required(finding_id, label="finding_id", max_chars=2048)
        sheet_key = _required(sheet_id, label="sheet_id", max_chars=128)
        if not isinstance(payload, bytes) or not payload:
            raise ChangeSheetTrustError("exact non-empty change sheet bytes are required for timestamping")
        digest = _digest(sheet_sha256)
        if sha256_hex(payload) != digest:
            raise ChangeSheetTrustError("change sheet bytes do not match supplied SHA-256 digest")
        status = self.capture_store.status(tenant_id=tenant, finding_id=finding)
        if str(status["sheet_id"]) != sheet_key:
            raise ChangeSheetTrustError("change sheet id does not belong to the tenant-scoped finding")
        subject_ref = self._subject_ref(sheet_key, digest)
        existing = self._existing_verified(tenant_id=tenant, finding_id=finding, digest=digest)
        if existing is not None:
            return self._public_attestation(existing)

        provider_name = str(getattr(self.provider, "name", "") or "").strip()
        if provider_name == "UNCONFIGURED":
            with self._connect() as conn:
                unavailable = conn.execute(
                    """SELECT * FROM causledger_change_sheet_attestations
                       WHERE tenant_id=? AND finding_id=? AND sheet_sha256=?
                         AND kind='QUALIFIED_TIMESTAMP' AND provider='UNCONFIGURED' AND state='UNAVAILABLE'
                       ORDER BY recorded_at DESC,attestation_id DESC LIMIT 1""",
                    (tenant, finding, digest),
                ).fetchone()
            if unavailable is not None:
                self._row_attestation(unavailable)
                return self._public_attestation(unavailable)

        if str(getattr(self.provider, "kind", "") or "") != "QUALIFIED_TIMESTAMP":
            raise ChangeSheetTrustError("configured change sheet provider is not a qualified timestamp provider")
        request = ProofRequest(
            tenant_id=tenant,
            subject_ref=subject_ref,
            digest_algorithm="SHA-256",
            digest=digest,
            purpose=self._purpose(),
            metadata={
                "subject_ref": subject_ref, "purpose": self._purpose(), "sheet_id": sheet_key,
                "finding_id": finding, "factual_window_closes_at": str(factual_window_closes_at),
                "payload_sha256_locally_verified": True,
            },
            payload=payload,
        )
        attestation = self.provider.attest(request)
        self._validate_attestation(attestation=attestation, expected_digest=digest, expected_subject_ref=subject_ref)
        recorded_at = _utc_now()
        body = {
            "tenant_id": tenant, "finding_id": finding, "sheet_id": sheet_key,
            "sheet_sha256": digest, "subject_ref": subject_ref,
            "attestation": attestation.as_dict(), "recorded_at": recorded_at,
        }
        attestation_hash = sha256_hex(body)
        attestation_id = f"sheettsa_{attestation_hash[:24]}"
        details_json = canonical_json_bytes(dict(attestation.details or {})).decode("utf-8")
        with self._connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO causledger_change_sheet_attestations(
                    attestation_id,attestation_hash,tenant_id,finding_id,sheet_id,sheet_sha256,
                    subject_ref,kind,provider,state,digest_algorithm,provider_ref,issued_at,
                    validation_ref,details_json,recorded_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (attestation_id, attestation_hash, tenant, finding, sheet_key, digest, subject_ref,
                 attestation.kind, attestation.provider, str(attestation.state).upper(),
                 attestation.digest_algorithm.upper(), attestation.provider_ref, attestation.issued_at,
                 attestation.validation_ref, details_json, recorded_at),
            )
            row = conn.execute(
                "SELECT * FROM causledger_change_sheet_attestations WHERE attestation_hash=?",
                (attestation_hash,),
            ).fetchone()
        if row is None:
            raise ChangeSheetTrustError("change sheet time attestation could not be persisted")
        self._row_attestation(row)
        return self._public_attestation(row)

    def attest_current(self, *, tenant_id: str, finding_id: str) -> dict[str, Any]:
        status, payload, digest, _subject_ref = self._current_snapshot(tenant_id=tenant_id, finding_id=finding_id)
        return self.attest_snapshot(
            tenant_id=tenant_id, finding_id=finding_id, sheet_id=str(status["sheet_id"]), payload=payload,
            sheet_sha256=digest, factual_window_closes_at=str(status["factual_window_closes_at"]),
        )

    def status(self, *, tenant_id: str, finding_id: str) -> dict[str, Any]:
        tenant = _required(tenant_id, label="tenant_id", max_chars=64)
        finding = _required(finding_id, label="finding_id", max_chars=2048)
        capture, _payload, digest, subject_ref = self._current_snapshot(tenant_id=tenant, finding_id=finding)
        with self._connect() as conn:
            rows = list(conn.execute(
                """SELECT * FROM causledger_change_sheet_attestations
                   WHERE tenant_id=? AND finding_id=? ORDER BY recorded_at,attestation_id""",
                (tenant, finding),
            ).fetchall())
        for row in rows:
            self._row_attestation(row)
        current = [row for row in rows if str(row["sheet_sha256"]) == digest]
        current_verified = [row for row in current if str(row["state"]).upper() in _VERIFIED_STATES]
        latest = current_verified[-1] if current_verified else (current[-1] if current else None)
        historical_digests = {str(row["sheet_sha256"]) for row in rows if str(row["sheet_sha256"]) != digest}
        return {
            "sheet_id": str(capture["sheet_id"]), "current_snapshot_sha256": digest,
            "current_subject_ref": subject_ref,
            "current_timestamp": None if latest is None else self._public_attestation(latest),
            "current_snapshot_externally_timestamped": bool(current_verified),
            "historical_attested_snapshot_count": len(historical_digests),
            "stale_attestation_exists_for_older_snapshot": bool(historical_digests),
            "timestamp_receipts_revalidated_on_read": True, "timestamp_is_digest_specific": True,
            "timestamp_binds_exact_snapshot_bytes": True, "new_fact_requires_new_timestamp": True,
            "qualified_timestamp_claim_is_fail_closed": True,
            "declared_change_requested_at_is_not_upgraded_by_sheet_timestamp": True,
        }