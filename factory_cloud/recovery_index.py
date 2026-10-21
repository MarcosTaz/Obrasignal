from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from factory_cloud.recovery_primitives import EntitlementBasis, RecoveryFingerprint


class RecoveryIndexError(RuntimeError):
    pass


class RecoveryIndex:
    """Consumer-owned durable index for entitlement basis and duplicate prevention."""

    def __init__(self, database: str | Path):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS entitlement_basis(
                    entitlement_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, domain TEXT NOT NULL,
                    source_evidence_ids_json TEXT NOT NULL, rule_ref TEXT NOT NULL,
                    confidence TEXT NOT NULL, basis_hash TEXT NOT NULL
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entitlement_tenant ON entitlement_basis(tenant_id,entitlement_id)")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS recovery_fingerprints(
                    tenant_id TEXT NOT NULL, fingerprint TEXT NOT NULL, vertical TEXT NOT NULL,
                    contract_ref TEXT NOT NULL, event_ref TEXT NOT NULL, remedy_type TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,fingerprint)
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _json(value) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def put_entitlement(self, item: EntitlementBasis) -> None:
        values = (item.entitlement_id, item.tenant_id, item.domain, self._json(item.source_evidence_ids), item.rule_ref, item.confidence, item.basis_hash)
        with self._connect() as conn:
            existing = conn.execute("SELECT * FROM entitlement_basis WHERE entitlement_id=?", (item.entitlement_id,)).fetchone()
            if existing:
                current = tuple(existing[key] for key in ("entitlement_id","tenant_id","domain","source_evidence_ids_json","rule_ref","confidence","basis_hash"))
                if current != values:
                    raise RecoveryIndexError("immutable entitlement basis collision")
                return
            conn.execute("INSERT INTO entitlement_basis VALUES(?,?,?,?,?,?,?)", values)

    def register_fingerprint(self, item: RecoveryFingerprint) -> bool:
        values = (item.tenant_id, item.fingerprint, item.vertical, item.contract_ref, item.event_ref, item.remedy_type)
        with self._connect() as conn:
            existing = conn.execute("SELECT * FROM recovery_fingerprints WHERE tenant_id=? AND fingerprint=?", (item.tenant_id, item.fingerprint)).fetchone()
            if existing:
                current = tuple(existing[key] for key in ("tenant_id","fingerprint","vertical","contract_ref","event_ref","remedy_type"))
                if current != values:
                    raise RecoveryIndexError("recovery fingerprint collision")
                return False
            conn.execute("INSERT INTO recovery_fingerprints VALUES(?,?,?,?,?,?)", values)
            return True

    def persist_case_index(self, entitlement: EntitlementBasis, fingerprint: RecoveryFingerprint) -> bool:
        if entitlement.tenant_id != fingerprint.tenant_id:
            raise RecoveryIndexError("cross-tenant recovery index rejected")
        self.put_entitlement(entitlement)
        return self.register_fingerprint(fingerprint)

    def count_fingerprints(self, tenant_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM recovery_fingerprints WHERE tenant_id=?", (tenant_id,)).fetchone()
        return int(row["n"])
