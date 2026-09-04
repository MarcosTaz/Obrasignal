from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vertical_apps.industrial_claims.leakage_reconciliation import RecoveryLedgerSnapshot


class RecoveryReconciliationStoreError(ValueError):
    pass


MAX_ID_CHARS = 2048
MAX_ACTOR_CHARS = 256
MAX_EVIDENCE_REF_CHARS = 2048
MAX_REASON_CHARS = 4000
_DECREASE_FIELDS = (
    "net_documented_exposure",
    "evidence_supported",
    "claimed",
    "approved",
    "settled",
)


def _text(value: object, *, label: str, max_chars: int, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise RecoveryReconciliationStoreError(f"{label} is required")
    if len(text) > max_chars:
        raise RecoveryReconciliationStoreError(f"{label} exceeds {max_chars} characters")
    if any((ord(char) < 32 and char not in "\t\n\r") or ord(char) == 127 for char in text):
        raise RecoveryReconciliationStoreError(f"{label} contains forbidden control characters")
    return text


@dataclass(frozen=True)
class PersistedRecoveryReconciliation:
    tenant_id: str
    finding_id: str
    sequence: int
    reconciliation_hash: str
    snapshot: dict[str, Any]
    actor_id: str
    evidence_ref: str
    reversal_reason: str | None
    created_at: str


class RecoveryReconciliationStore:
    """Append-only tenant-scoped recovery-ledger history.

    Economic regressions are not silently rejected because real claims can be
    corrected, reduced, refunded or clawed back. Any decrease in a material stage
    requires an explicit evidence reference and reversal/correction reason.
    """

    def __init__(self, database: str | Path):
        self.path = str(database)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS industrial_recovery_reconciliations (
                    tenant_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    reconciliation_hash TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    reversal_reason TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tenant_id, finding_id, sequence),
                    UNIQUE (tenant_id, finding_id, reconciliation_hash)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_industrial_recovery_reconciliations_latest
                ON industrial_recovery_reconciliations (tenant_id, finding_id, sequence DESC)
                """
            )
            connection.commit()

    @staticmethod
    def _decode(row: sqlite3.Row) -> PersistedRecoveryReconciliation:
        try:
            snapshot = json.loads(row["snapshot_json"])
        except (TypeError, ValueError) as exc:
            raise RecoveryReconciliationStoreError("persisted reconciliation snapshot is invalid") from exc
        if not isinstance(snapshot, dict):
            raise RecoveryReconciliationStoreError("persisted reconciliation snapshot must be an object")
        return PersistedRecoveryReconciliation(
            tenant_id=str(row["tenant_id"]),
            finding_id=str(row["finding_id"]),
            sequence=int(row["sequence"]),
            reconciliation_hash=str(row["reconciliation_hash"]),
            snapshot=snapshot,
            actor_id=str(row["actor_id"]),
            evidence_ref=str(row["evidence_ref"]),
            reversal_reason=str(row["reversal_reason"]) if row["reversal_reason"] is not None else None,
            created_at=str(row["created_at"]),
        )

    def latest(self, *, tenant_id: str, finding_id: str) -> PersistedRecoveryReconciliation | None:
        tenant = _text(tenant_id, label="tenant_id", max_chars=64)
        finding = _text(finding_id, label="finding_id", max_chars=MAX_ID_CHARS)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM industrial_recovery_reconciliations
                WHERE tenant_id=? AND finding_id=?
                ORDER BY sequence DESC LIMIT 1
                """,
                (tenant, finding),
            ).fetchone()
        return self._decode(row) if row is not None else None

    @staticmethod
    def _decreased(previous: dict[str, Any], current: dict[str, Any]) -> tuple[str, ...]:
        from decimal import Decimal, InvalidOperation

        decreased: list[str] = []
        for field in _DECREASE_FIELDS:
            try:
                before = Decimal(str(previous[field]))
                after = Decimal(str(current[field]))
            except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
                raise RecoveryReconciliationStoreError(f"invalid persisted amount for {field}") from exc
            if after < before:
                decreased.append(field)
        return tuple(decreased)

    def append(
        self,
        *,
        tenant_id: str,
        finding_id: str,
        snapshot: RecoveryLedgerSnapshot,
        actor_id: str,
        evidence_ref: str,
        reversal_reason: str | None = None,
    ) -> PersistedRecoveryReconciliation:
        tenant = _text(tenant_id, label="tenant_id", max_chars=64)
        finding = _text(finding_id, label="finding_id", max_chars=MAX_ID_CHARS)
        actor = _text(actor_id, label="actor_id", max_chars=MAX_ACTOR_CHARS)
        evidence = _text(evidence_ref, label="evidence_ref", max_chars=MAX_EVIDENCE_REF_CHARS)
        reason = _text(reversal_reason, label="reversal_reason", max_chars=MAX_REASON_CHARS, required=False) or None
        if not isinstance(snapshot, RecoveryLedgerSnapshot):
            raise RecoveryReconciliationStoreError("snapshot must be a RecoveryLedgerSnapshot")

        payload = snapshot.as_dict()
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            replay = connection.execute(
                """
                SELECT * FROM industrial_recovery_reconciliations
                WHERE tenant_id=? AND finding_id=? AND reconciliation_hash=?
                """,
                (tenant, finding, snapshot.reconciliation_hash),
            ).fetchone()
            if replay is not None:
                existing = self._decode(replay)
                if existing.actor_id != actor or existing.evidence_ref != evidence or existing.reversal_reason != reason:
                    raise RecoveryReconciliationStoreError("reconciliation hash replay metadata does not match persisted record")
                connection.commit()
                return existing

            previous_row = connection.execute(
                """
                SELECT * FROM industrial_recovery_reconciliations
                WHERE tenant_id=? AND finding_id=?
                ORDER BY sequence DESC LIMIT 1
                """,
                (tenant, finding),
            ).fetchone()
            sequence = 1
            if previous_row is not None:
                previous = self._decode(previous_row)
                sequence = previous.sequence + 1
                decreased = self._decreased(previous.snapshot, payload)
                if decreased and not reason:
                    raise RecoveryReconciliationStoreError(
                        "economic decrease requires reversal_reason: " + ",".join(decreased)
                    )

            connection.execute(
                """
                INSERT INTO industrial_recovery_reconciliations (
                    tenant_id,finding_id,sequence,reconciliation_hash,snapshot_json,
                    actor_id,evidence_ref,reversal_reason
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (tenant, finding, sequence, snapshot.reconciliation_hash, payload_json, actor, evidence, reason),
            )
            row = connection.execute(
                """
                SELECT * FROM industrial_recovery_reconciliations
                WHERE tenant_id=? AND finding_id=? AND sequence=?
                """,
                (tenant, finding, sequence),
            ).fetchone()
            connection.commit()

        if row is None:
            raise RecoveryReconciliationStoreError("reconciliation persistence failed")
        return self._decode(row)

    def history(self, *, tenant_id: str, finding_id: str) -> tuple[PersistedRecoveryReconciliation, ...]:
        tenant = _text(tenant_id, label="tenant_id", max_chars=64)
        finding = _text(finding_id, label="finding_id", max_chars=MAX_ID_CHARS)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM industrial_recovery_reconciliations
                WHERE tenant_id=? AND finding_id=?
                ORDER BY sequence ASC
                """,
                (tenant, finding),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)
