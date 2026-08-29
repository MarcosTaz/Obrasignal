from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from factory_cloud.assurance_store import AssuranceStoreError


@dataclass(frozen=True)
class IndustrialCaseMetadata:
    finding_id: str
    tenant_id: str
    claim_family: str
    customer_ref: str
    program_ref: str
    event_ref: str
    entitlement_id: str
    deadline_id: str
    recovery_fingerprint: str
    notice_deadline_state: str
    missing_evidence: tuple[str, ...]


class IndustrialClaimsCaseStore:
    """Durable Industrial-specific metadata needed to resume assisted cases.

    The store contains identifiers and truth-state metadata only; documentary
    content remains outside this table and is represented by immutable hashes in
    the shared evidence store.
    """

    def __init__(self, database: str | Path):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS industrial_claim_cases(
                    finding_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    claim_family TEXT NOT NULL,
                    customer_ref TEXT NOT NULL,
                    program_ref TEXT NOT NULL,
                    event_ref TEXT NOT NULL,
                    entitlement_id TEXT NOT NULL,
                    deadline_id TEXT NOT NULL,
                    recovery_fingerprint TEXT NOT NULL,
                    notice_deadline_state TEXT NOT NULL,
                    missing_evidence_json TEXT NOT NULL
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_industrial_claim_cases_tenant ON industrial_claim_cases(tenant_id,finding_id)"
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _values(item: IndustrialCaseMetadata) -> tuple[str, ...]:
        return (
            item.finding_id,
            item.tenant_id,
            item.claim_family,
            item.customer_ref,
            item.program_ref,
            item.event_ref,
            item.entitlement_id,
            item.deadline_id,
            item.recovery_fingerprint,
            item.notice_deadline_state,
            json.dumps(list(item.missing_evidence), sort_keys=True, separators=(",", ":")),
        )

    def _put(self, conn: sqlite3.Connection, item: IndustrialCaseMetadata) -> None:
        values = self._values(item)
        existing = conn.execute("SELECT * FROM industrial_claim_cases WHERE finding_id=?", (item.finding_id,)).fetchone()
        if existing is not None:
            keys = (
                "finding_id", "tenant_id", "claim_family", "customer_ref", "program_ref", "event_ref",
                "entitlement_id", "deadline_id", "recovery_fingerprint", "notice_deadline_state", "missing_evidence_json",
            )
            current = tuple(str(existing[key]) for key in keys)
            if current != values:
                raise AssuranceStoreError("immutable industrial case metadata collision")
            return
        conn.execute("INSERT INTO industrial_claim_cases VALUES(?,?,?,?,?,?,?,?,?,?,?)", values)

    def put(self, item: IndustrialCaseMetadata, *, connection: sqlite3.Connection | None = None) -> None:
        if connection is not None:
            self._put(connection, item)
            return
        with self._connect() as conn:
            self._put(conn, item)

    def get(self, *, tenant_id: str, finding_id: str) -> IndustrialCaseMetadata:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM industrial_claim_cases WHERE tenant_id=? AND finding_id=?",
                (tenant_id, finding_id),
            ).fetchone()
        if row is None:
            raise AssuranceStoreError("tenant-scoped industrial case metadata not found")
        try:
            missing = json.loads(row["missing_evidence_json"])
        except (TypeError, ValueError) as exc:
            raise AssuranceStoreError("industrial case missing-evidence lineage is invalid") from exc
        if not isinstance(missing, list):
            raise AssuranceStoreError("industrial case missing-evidence lineage is invalid")
        return IndustrialCaseMetadata(
            finding_id=str(row["finding_id"]), tenant_id=str(row["tenant_id"]), claim_family=str(row["claim_family"]),
            customer_ref=str(row["customer_ref"]), program_ref=str(row["program_ref"]), event_ref=str(row["event_ref"]),
            entitlement_id=str(row["entitlement_id"]), deadline_id=str(row["deadline_id"]),
            recovery_fingerprint=str(row["recovery_fingerprint"]), notice_deadline_state=str(row["notice_deadline_state"]),
            missing_evidence=tuple(str(item) for item in missing),
        )

    def count(self, tenant_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM industrial_claim_cases WHERE tenant_id=?", (tenant_id,)).fetchone()
        return int(row["n"])
