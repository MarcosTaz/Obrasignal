from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from vertical_apps.industrial_claims.proof import canonical_json_bytes, sha256_hex


@dataclass(frozen=True)
class ProofLedgerEvent:
    event_id: str
    tenant_id: str
    subject_ref: str
    event_type: str
    actor_id: str
    first_seen_at: str
    effective_at: str | None
    source_ref: str | None
    payload_sha256: str
    previous_chain_hash: str | None
    chain_hash: str


class ProofLedgerError(RuntimeError):
    pass


class IndustrialProofStore:
    """Append-only, hash-chained proof ledger.

    This is an application-level immutable ledger. It is not a substitute for
    external WORM storage or a qualified timestamp authority; those remain
    separate proof gates and are recorded as external attestations.
    """

    def __init__(self, database: str | Path):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS industrial_proof_events(
                    event_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    subject_ref TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    effective_at TEXT,
                    source_ref TEXT,
                    payload_json TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    previous_chain_hash TEXT,
                    chain_hash TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_industrial_proof_subject
                    ON industrial_proof_events(tenant_id,subject_ref,first_seen_at,event_id);
                CREATE TABLE IF NOT EXISTS industrial_proof_attestations(
                    attestation_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    subject_ref TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    state TEXT NOT NULL,
                    provider_ref TEXT,
                    issued_at TEXT,
                    digest_algorithm TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_industrial_attestation_subject
                    ON industrial_proof_attestations(tenant_id,subject_ref,kind,recorded_at);
                CREATE TABLE IF NOT EXISTS industrial_proof_certificates(
                    certificate_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    subject_ref TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    manifest_sha512 TEXT NOT NULL,
                    merkle_root_sha256 TEXT,
                    chain_head_sha256 TEXT,
                    state TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    supersedes_certificate_id TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_industrial_certificate_revision
                    ON industrial_proof_certificates(tenant_id,subject_ref,revision);
                CREATE TABLE IF NOT EXISTS industrial_proof_supersessions(
                    supersession_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    old_certificate_id TEXT NOT NULL,
                    new_certificate_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS industrial_proof_events_no_update
                    BEFORE UPDATE ON industrial_proof_events BEGIN SELECT RAISE(ABORT,'industrial proof events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS industrial_proof_events_no_delete
                    BEFORE DELETE ON industrial_proof_events BEGIN SELECT RAISE(ABORT,'industrial proof events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS industrial_proof_attestations_no_update
                    BEFORE UPDATE ON industrial_proof_attestations BEGIN SELECT RAISE(ABORT,'industrial proof attestations are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS industrial_proof_attestations_no_delete
                    BEFORE DELETE ON industrial_proof_attestations BEGIN SELECT RAISE(ABORT,'industrial proof attestations are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS industrial_proof_certificates_no_update
                    BEFORE UPDATE ON industrial_proof_certificates BEGIN SELECT RAISE(ABORT,'industrial proof certificates are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS industrial_proof_certificates_no_delete
                    BEFORE DELETE ON industrial_proof_certificates BEGIN SELECT RAISE(ABORT,'industrial proof certificates are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS industrial_proof_supersessions_no_update
                    BEFORE UPDATE ON industrial_proof_supersessions BEGIN SELECT RAISE(ABORT,'industrial proof supersessions are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS industrial_proof_supersessions_no_delete
                    BEFORE DELETE ON industrial_proof_supersessions BEGIN SELECT RAISE(ABORT,'industrial proof supersessions are append-only'); END;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _required(value: object, label: str, max_chars: int = 4096) -> str:
        text = str(value or "").strip()
        if not text or len(text) > max_chars or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
            raise ProofLedgerError(f"invalid {label}")
        return text

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_iso_optional(value: str | None, label: str) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ProofLedgerError(f"invalid {label}") from exc
        if parsed.tzinfo is None:
            raise ProofLedgerError(f"{label} must include timezone")
        return parsed.astimezone(timezone.utc).isoformat()

    def append_event(
        self,
        *,
        event_id: str,
        tenant_id: str,
        subject_ref: str,
        event_type: str,
        actor_id: str,
        payload: Mapping[str, Any],
        effective_at: str | None = None,
        source_ref: str | None = None,
        first_seen_at: str | None = None,
    ) -> ProofLedgerEvent:
        event_key = self._required(event_id, "event_id")
        tenant = self._required(tenant_id, "tenant_id", 128)
        subject = self._required(subject_ref, "subject_ref")
        kind = self._required(event_type, "event_type", 256)
        actor = self._required(actor_id, "actor_id", 256)
        effective = self._parse_iso_optional(effective_at, "effective_at")
        first_seen = self._parse_iso_optional(first_seen_at, "first_seen_at") or self._utc_now()
        source = self._required(source_ref, "source_ref") if source_ref is not None else None
        payload_json = canonical_json_bytes(dict(payload)).decode("utf-8")
        payload_hash = sha256_hex(payload_json.encode("utf-8"))

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            duplicate = conn.execute("SELECT * FROM industrial_proof_events WHERE event_id=?", (event_key,)).fetchone()
            if duplicate is not None:
                raise ProofLedgerError("proof event id already exists")
            previous = conn.execute(
                """SELECT chain_hash FROM industrial_proof_events
                   WHERE tenant_id=? AND subject_ref=?
                   ORDER BY first_seen_at DESC,event_id DESC LIMIT 1""",
                (tenant, subject),
            ).fetchone()
            previous_hash = str(previous["chain_hash"]) if previous else None
            chain_payload = {
                "event_id": event_key,
                "tenant_id": tenant,
                "subject_ref": subject,
                "event_type": kind,
                "actor_id": actor,
                "first_seen_at": first_seen,
                "effective_at": effective,
                "source_ref": source,
                "payload_sha256": payload_hash,
                "previous_chain_hash": previous_hash,
            }
            chain_hash = sha256_hex(chain_payload)
            conn.execute(
                """INSERT INTO industrial_proof_events(
                    event_id,tenant_id,subject_ref,event_type,actor_id,first_seen_at,effective_at,
                    source_ref,payload_json,payload_sha256,previous_chain_hash,chain_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (event_key, tenant, subject, kind, actor, first_seen, effective, source, payload_json, payload_hash, previous_hash, chain_hash),
            )
            conn.commit()
        return ProofLedgerEvent(event_key, tenant, subject, kind, actor, first_seen, effective, source, payload_hash, previous_hash, chain_hash)

    def verify_chain(self, *, tenant_id: str, subject_ref: str) -> dict[str, Any]:
        tenant = self._required(tenant_id, "tenant_id", 128)
        subject = self._required(subject_ref, "subject_ref")
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM industrial_proof_events
                   WHERE tenant_id=? AND subject_ref=? ORDER BY first_seen_at,event_id""",
                (tenant, subject),
            ).fetchall()
        previous: str | None = None
        errors: list[str] = []
        for index, row in enumerate(rows):
            try:
                payload = json.loads(row["payload_json"])
            except (TypeError, ValueError):
                errors.append(f"EVENT_{index}_PAYLOAD_JSON_INVALID")
                continue
            if sha256_hex(canonical_json_bytes(payload)) != row["payload_sha256"]:
                errors.append(f"EVENT_{index}_PAYLOAD_HASH_MISMATCH")
            if row["previous_chain_hash"] != previous:
                errors.append(f"EVENT_{index}_PREVIOUS_HASH_MISMATCH")
            chain_payload = {
                "event_id": row["event_id"],
                "tenant_id": row["tenant_id"],
                "subject_ref": row["subject_ref"],
                "event_type": row["event_type"],
                "actor_id": row["actor_id"],
                "first_seen_at": row["first_seen_at"],
                "effective_at": row["effective_at"],
                "source_ref": row["source_ref"],
                "payload_sha256": row["payload_sha256"],
                "previous_chain_hash": row["previous_chain_hash"],
            }
            expected = sha256_hex(chain_payload)
            if expected != row["chain_hash"]:
                errors.append(f"EVENT_{index}_CHAIN_HASH_MISMATCH")
            previous = str(row["chain_hash"])
        return {"valid": not errors, "errors": errors, "event_count": len(rows), "chain_head_sha256": previous}

    def record_attestation(
        self,
        *,
        attestation_id: str,
        tenant_id: str,
        subject_ref: str,
        kind: str,
        provider: str,
        state: str,
        digest_algorithm: str,
        digest: str,
        payload: Mapping[str, Any],
        provider_ref: str | None = None,
        issued_at: str | None = None,
    ) -> None:
        attestation = self._required(attestation_id, "attestation_id")
        tenant = self._required(tenant_id, "tenant_id", 128)
        subject = self._required(subject_ref, "subject_ref")
        proof_kind = self._required(kind, "kind", 128)
        provider_name = self._required(provider, "provider", 256)
        proof_state = self._required(state, "state", 64).upper()
        algorithm = self._required(digest_algorithm, "digest_algorithm", 32).upper()
        digest_value = self._required(digest, "digest", 256).lower()
        if algorithm not in {"SHA-256", "SHA-512"}:
            raise ProofLedgerError("unsupported digest algorithm")
        expected_length = 64 if algorithm == "SHA-256" else 128
        if len(digest_value) != expected_length or any(c not in "0123456789abcdef" for c in digest_value):
            raise ProofLedgerError("invalid attestation digest")
        provider_reference = self._required(provider_ref, "provider_ref") if provider_ref else None
        if proof_state in {"VALID", "VERIFIED"} and not provider_reference:
            raise ProofLedgerError("verified attestation requires provider reference")
        issued = self._parse_iso_optional(issued_at, "issued_at")
        payload_json = canonical_json_bytes(dict(payload)).decode("utf-8")
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO industrial_proof_attestations(
                    attestation_id,tenant_id,subject_ref,kind,provider,state,provider_ref,issued_at,
                    digest_algorithm,digest,payload_json,recorded_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (attestation, tenant, subject, proof_kind, provider_name, proof_state, provider_reference, issued, algorithm, digest_value, payload_json, self._utc_now()),
            )

    def issue_certificate(
        self,
        *,
        certificate_id: str,
        tenant_id: str,
        subject_ref: str,
        revision: int,
        manifest_sha256: str,
        manifest_sha512: str,
        merkle_root_sha256: str | None,
        state: str,
        supersedes_certificate_id: str | None = None,
    ) -> None:
        certificate = self._required(certificate_id, "certificate_id")
        tenant = self._required(tenant_id, "tenant_id", 128)
        subject = self._required(subject_ref, "subject_ref")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ProofLedgerError("invalid proof certificate revision")
        if len(manifest_sha256) != 64 or len(manifest_sha512) != 128:
            raise ProofLedgerError("invalid manifest digests")
        chain = self.verify_chain(tenant_id=tenant, subject_ref=subject)
        if not chain["valid"]:
            raise ProofLedgerError("cannot issue proof certificate over invalid chain")
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO industrial_proof_certificates(
                    certificate_id,tenant_id,subject_ref,revision,manifest_sha256,manifest_sha512,
                    merkle_root_sha256,chain_head_sha256,state,issued_at,supersedes_certificate_id
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (certificate, tenant, subject, revision, manifest_sha256, manifest_sha512, merkle_root_sha256, chain["chain_head_sha256"], self._required(state, "state", 64), self._utc_now(), supersedes_certificate_id),
            )

    def supersede_certificate(
        self,
        *,
        supersession_id: str,
        tenant_id: str,
        old_certificate_id: str,
        new_certificate_id: str,
        reason: str,
        actor_id: str,
    ) -> None:
        if old_certificate_id == new_certificate_id:
            raise ProofLedgerError("certificate cannot supersede itself")
        with self._connect() as conn:
            old = conn.execute("SELECT tenant_id FROM industrial_proof_certificates WHERE certificate_id=?", (old_certificate_id,)).fetchone()
            new = conn.execute("SELECT tenant_id,supersedes_certificate_id FROM industrial_proof_certificates WHERE certificate_id=?", (new_certificate_id,)).fetchone()
            if old is None or new is None:
                raise ProofLedgerError("certificate supersession requires both certificates")
            tenant = self._required(tenant_id, "tenant_id", 128)
            if old["tenant_id"] != tenant or new["tenant_id"] != tenant:
                raise ProofLedgerError("cross-tenant certificate supersession rejected")
            if new["supersedes_certificate_id"] != old_certificate_id:
                raise ProofLedgerError("new certificate does not declare old certificate as predecessor")
            conn.execute(
                """INSERT INTO industrial_proof_supersessions(
                    supersession_id,tenant_id,old_certificate_id,new_certificate_id,reason,actor_id,recorded_at
                ) VALUES(?,?,?,?,?,?,?)""",
                (self._required(supersession_id, "supersession_id"), tenant, old_certificate_id, new_certificate_id, self._required(reason, "reason"), self._required(actor_id, "actor_id", 256), self._utc_now()),
            )
