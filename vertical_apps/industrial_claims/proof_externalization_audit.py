from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from vertical_apps.industrial_claims.proof import canonical_json_bytes, sha256_hex


class ProofExternalizationAuditError(RuntimeError):
    pass


_ALLOWED_STATES = {"STARTED", "COMPLETED", "FAILED"}
_MAX_PAYLOAD_BYTES = 32_768


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _required(value: object, *, label: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ProofExternalizationAuditError(f"invalid {label}")
    return text


def _digest(value: object) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ProofExternalizationAuditError("invalid proof target SHA-256")
    return text


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ProofExternalizationAuditError("externalization audit clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _payload(value: Mapping[str, Any] | None) -> tuple[dict[str, Any], str]:
    normalized = dict(value or {})
    encoded = canonical_json_bytes(normalized)
    if len(encoded) > _MAX_PAYLOAD_BYTES:
        raise ProofExternalizationAuditError("externalization audit payload is too large")
    return normalized, encoded.decode("utf-8")


class ProofExternalizationAuditStore:
    """Append-only operation ledger around external proof side effects.

    STARTED is written before any external provider is invoked. Exactly one
    COMPLETED or FAILED event may close an operation. The per-case hash chain is
    revalidated before each append and on reads so a later database edit cannot
    silently erase or rewrite a partially completed external proof operation.
    """

    def __init__(self, database: str | Path, *, clock: Callable[[], datetime] = _now) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS causledger_proof_externalization_events(
                    sequence INTEGER PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    operation_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    target_sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_event_hash TEXT,
                    event_hash TEXT NOT NULL UNIQUE,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_causledger_proof_externalization_case
                    ON causledger_proof_externalization_events(tenant_id,finding_id,sequence);
                CREATE INDEX IF NOT EXISTS idx_causledger_proof_externalization_operation
                    ON causledger_proof_externalization_events(operation_id,sequence);
                CREATE TRIGGER IF NOT EXISTS causledger_proof_externalization_no_update
                    BEFORE UPDATE ON causledger_proof_externalization_events
                    BEGIN SELECT RAISE(ABORT,'proof externalization events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_proof_externalization_no_delete
                    BEFORE DELETE ON causledger_proof_externalization_events
                    BEGIN SELECT RAISE(ABORT,'proof externalization events are append-only'); END;
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _body(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "sequence": int(row["sequence"]),
            "event_id": str(row["event_id"]),
            "operation_id": str(row["operation_id"]),
            "tenant_id": str(row["tenant_id"]),
            "finding_id": str(row["finding_id"]),
            "actor_id": str(row["actor_id"]),
            "state": str(row["state"]),
            "target_sha256": str(row["target_sha256"]),
            "payload": json.loads(str(row["payload_json"])),
            "previous_event_hash": row["previous_event_hash"],
            "recorded_at": str(row["recorded_at"]),
        }

    def _verify_rows(self, rows: list[sqlite3.Row]) -> str | None:
        previous: str | None = None
        seen_sequences: set[int] = set()
        for row in rows:
            sequence = int(row["sequence"])
            if sequence in seen_sequences:
                raise ProofExternalizationAuditError("duplicate externalization ledger sequence")
            seen_sequences.add(sequence)
            if row["previous_event_hash"] != previous:
                raise ProofExternalizationAuditError("externalization ledger previous-hash mismatch")
            try:
                body = self._body(row)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ProofExternalizationAuditError("externalization ledger payload is invalid") from exc
            expected = sha256_hex(body)
            if str(row["event_hash"]) != expected:
                raise ProofExternalizationAuditError("externalization ledger event hash mismatch")
            previous = expected
        return previous

    def _case_rows(self, conn: sqlite3.Connection, *, tenant_id: str, finding_id: str) -> list[sqlite3.Row]:
        return list(
            conn.execute(
                """SELECT * FROM causledger_proof_externalization_events
                   WHERE tenant_id=? AND finding_id=? ORDER BY sequence""",
                (tenant_id, finding_id),
            ).fetchall()
        )

    def _append(
        self,
        conn: sqlite3.Connection,
        *,
        operation_id: str,
        tenant_id: str,
        finding_id: str,
        actor_id: str,
        state: str,
        target_sha256: str,
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        rows = self._case_rows(conn, tenant_id=tenant_id, finding_id=finding_id)
        previous = self._verify_rows(rows)
        next_sequence = int(conn.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 AS n FROM causledger_proof_externalization_events"
        ).fetchone()["n"])
        event_id = f"proofext_evt_{secrets.token_urlsafe(18)}"
        normalized_payload, payload_json = _payload(payload)
        recorded_at = _iso(self.clock())
        body = {
            "sequence": next_sequence,
            "event_id": event_id,
            "operation_id": operation_id,
            "tenant_id": tenant_id,
            "finding_id": finding_id,
            "actor_id": actor_id,
            "state": state,
            "target_sha256": target_sha256,
            "payload": normalized_payload,
            "previous_event_hash": previous,
            "recorded_at": recorded_at,
        }
        event_hash = sha256_hex(body)
        conn.execute(
            """INSERT INTO causledger_proof_externalization_events(
                sequence,event_id,operation_id,tenant_id,finding_id,actor_id,state,
                target_sha256,payload_json,previous_event_hash,event_hash,recorded_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                next_sequence,event_id,operation_id,tenant_id,finding_id,actor_id,state,
                target_sha256,payload_json,previous,event_hash,recorded_at,
            ),
        )
        return {**body, "event_hash": event_hash}

    def start(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        actor_id: str,
        target_sha256: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        finding = _required(finding_id, label="finding_id")
        actor = _required(actor_id, label="actor_id", maximum=256)
        target = _digest(target_sha256)
        operation_id = f"proofext_{secrets.token_urlsafe(18)}"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            result = self._append(
                conn,
                operation_id=operation_id,
                tenant_id=tenant,
                finding_id=finding,
                actor_id=actor,
                state="STARTED",
                target_sha256=target,
                payload=payload,
            )
            conn.commit()
        return result

    def finish(
        self,
        *,
        operation_id: str,
        tenant_id: str,
        finding_id: str,
        actor_id: str,
        state: str,
        target_sha256: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        operation = _required(operation_id, label="operation_id", maximum=256)
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        finding = _required(finding_id, label="finding_id")
        actor = _required(actor_id, label="actor_id", maximum=256)
        target = _digest(target_sha256)
        terminal = str(state or "").strip().upper()
        if terminal not in {"COMPLETED", "FAILED"}:
            raise ProofExternalizationAuditError("externalization finish state must be COMPLETED or FAILED")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            operation_rows = list(conn.execute(
                """SELECT * FROM causledger_proof_externalization_events
                   WHERE operation_id=? ORDER BY sequence""",
                (operation,),
            ).fetchall())
            if len(operation_rows) != 1 or str(operation_rows[0]["state"]) != "STARTED":
                raise ProofExternalizationAuditError("externalization operation is missing, ambiguous, or already closed")
            started = operation_rows[0]
            if (
                str(started["tenant_id"]) != tenant
                or str(started["finding_id"]) != finding
                or str(started["actor_id"]) != actor
                or str(started["target_sha256"]) != target
            ):
                raise ProofExternalizationAuditError("externalization terminal event does not match started operation")
            result = self._append(
                conn,
                operation_id=operation,
                tenant_id=tenant,
                finding_id=finding,
                actor_id=actor,
                state=terminal,
                target_sha256=target,
                payload=payload,
            )
            conn.commit()
        return result

    def status(self, *, tenant_id: str, finding_id: str) -> dict[str, Any]:
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        finding = _required(finding_id, label="finding_id")
        with self._connect() as conn:
            rows = self._case_rows(conn, tenant_id=tenant, finding_id=finding)
        head = self._verify_rows(rows)
        operations: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            body = self._body(row)
            body["event_hash"] = str(row["event_hash"])
            operations.setdefault(str(row["operation_id"]), []).append(body)
        return {
            "event_count": len(rows),
            "chain_head_sha256": head,
            "chain_valid": True,
            "operations": operations,
            "append_only": True,
        }
