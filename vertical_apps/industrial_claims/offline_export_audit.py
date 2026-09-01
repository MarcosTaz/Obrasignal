from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from vertical_apps.industrial_claims.proof import canonical_json_bytes, sha256_hex


class OfflineExportAuditError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _required(value: object, *, label: str, maximum: int = 4096) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise OfflineExportAuditError(f"invalid offline export {label}")
    return text


def _digest(value: object, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise OfflineExportAuditError(f"invalid offline export {label}")
    return text


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise OfflineExportAuditError("offline export audit clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _payload(value: Mapping[str, Any] | None) -> tuple[dict[str, Any], str]:
    normalized = dict(value or {})
    encoded = canonical_json_bytes(normalized)
    if len(encoded) > 16_384:
        raise OfflineExportAuditError("offline export audit payload is too large")
    forbidden = {
        "content",
        "content_base64",
        "raw_content",
        "original_bytes",
        "document",
        "documents",
    }
    if any(str(key).strip().lower() in forbidden for key in normalized):
        raise OfflineExportAuditError("offline export audit payload cannot contain documentary content")
    return normalized, encoded.decode("utf-8")


class OfflineExportAuditStore:
    """Append-only hash-chained ledger for confidential bundle release attempts.

    The ledger records metadata only. Documentary bytes and base64 payloads are
    explicitly forbidden. STARTED is appended immediately before immutable-store
    reads; COMPLETED is appended only after independent bundle verification passes.
    """

    def __init__(self, database: str | Path, *, clock: Callable[[], datetime] = _now) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS causledger_offline_export_events(
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
                CREATE INDEX IF NOT EXISTS idx_causledger_offline_export_case
                    ON causledger_offline_export_events(tenant_id,finding_id,sequence);
                CREATE INDEX IF NOT EXISTS idx_causledger_offline_export_operation
                    ON causledger_offline_export_events(operation_id,sequence);
                CREATE TRIGGER IF NOT EXISTS causledger_offline_export_no_update
                    BEFORE UPDATE ON causledger_offline_export_events
                    BEGIN SELECT RAISE(ABORT,'offline export events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS causledger_offline_export_no_delete
                    BEFORE DELETE ON causledger_offline_export_events
                    BEGIN SELECT RAISE(ABORT,'offline export events are append-only'); END;
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

    def _rows(self, conn: sqlite3.Connection, *, tenant_id: str, finding_id: str) -> list[sqlite3.Row]:
        return list(conn.execute(
            "SELECT * FROM causledger_offline_export_events WHERE tenant_id=? AND finding_id=? ORDER BY sequence",
            (tenant_id, finding_id),
        ).fetchall())

    def _verify(self, rows: list[sqlite3.Row]) -> str | None:
        previous: str | None = None
        for row in rows:
            if row["previous_event_hash"] != previous:
                raise OfflineExportAuditError("offline export audit previous-hash mismatch")
            try:
                body = self._body(row)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise OfflineExportAuditError("offline export audit payload is invalid") from exc
            expected = sha256_hex(body)
            if str(row["event_hash"]) != expected:
                raise OfflineExportAuditError("offline export audit event hash mismatch")
            previous = expected
        return previous

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
        rows = self._rows(conn, tenant_id=tenant_id, finding_id=finding_id)
        previous = self._verify(rows)
        sequence = int(conn.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 AS n FROM causledger_offline_export_events"
        ).fetchone()["n"])
        event_id = f"offexp_evt_{secrets.token_urlsafe(18)}"
        normalized, payload_json = _payload(payload)
        recorded_at = _iso(self.clock())
        body = {
            "sequence": sequence,
            "event_id": event_id,
            "operation_id": operation_id,
            "tenant_id": tenant_id,
            "finding_id": finding_id,
            "actor_id": actor_id,
            "state": state,
            "target_sha256": target_sha256,
            "payload": normalized,
            "previous_event_hash": previous,
            "recorded_at": recorded_at,
        }
        event_hash = sha256_hex(body)
        conn.execute(
            "INSERT INTO causledger_offline_export_events(sequence,event_id,operation_id,tenant_id,finding_id,actor_id,state,target_sha256,payload_json,previous_event_hash,event_hash,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (sequence,event_id,operation_id,tenant_id,finding_id,actor_id,state,target_sha256,payload_json,previous,event_hash,recorded_at),
        )
        return {**body, "event_hash": event_hash}

    def start(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        actor_id: str,
        target_sha256: str,
        evidence_count: int,
    ) -> dict[str, Any]:
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        finding = _required(finding_id, label="finding_id")
        actor = _required(actor_id, label="actor_id", maximum=256)
        target = _digest(target_sha256, label="target SHA-256")
        if not isinstance(evidence_count, int) or evidence_count < 1:
            raise OfflineExportAuditError("offline export evidence count is invalid")
        operation_id = f"offexp_{secrets.token_urlsafe(18)}"
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
                payload={"evidence_count": evidence_count, "contains_documentary_bytes": False},
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
        target_sha256: str,
        state: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        operation = _required(operation_id, label="operation_id", maximum=256)
        tenant = _required(tenant_id, label="tenant_id", maximum=64)
        finding = _required(finding_id, label="finding_id")
        actor = _required(actor_id, label="actor_id", maximum=256)
        target = _digest(target_sha256, label="target SHA-256")
        terminal = str(state or "").strip().upper()
        if terminal not in {"COMPLETED", "FAILED"}:
            raise OfflineExportAuditError("offline export terminal state must be COMPLETED or FAILED")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            operation_rows = list(conn.execute(
                "SELECT * FROM causledger_offline_export_events WHERE operation_id=? ORDER BY sequence",
                (operation,),
            ).fetchall())
            if len(operation_rows) != 1 or str(operation_rows[0]["state"]) != "STARTED":
                raise OfflineExportAuditError("offline export operation is missing, ambiguous, or already closed")
            started = operation_rows[0]
            if (
                str(started["tenant_id"]) != tenant
                or str(started["finding_id"]) != finding
                or str(started["actor_id"]) != actor
                or str(started["target_sha256"]) != target
            ):
                raise OfflineExportAuditError("offline export terminal event does not match started operation")
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
            rows = self._rows(conn, tenant_id=tenant, finding_id=finding)
        head = self._verify(rows)
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
            "documentary_content_stored": False,
        }
