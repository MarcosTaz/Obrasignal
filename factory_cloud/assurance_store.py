from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from factory_cloud.assurance_kernel import CalculationRecord, DeadlineWindow, EvidenceEnvelope, FindingRecord
from factory_cloud.shared_platform import AuditEvent, NotificationEvent

SCHEMA_VERSION = 1


class AssuranceStoreError(RuntimeError):
    pass


class AssuranceStore:
    """Durable app-neutral assurance persistence with tenant-scoped reads."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS assurance_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evidence(
                    evidence_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL, received_at TEXT NOT NULL, content_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_tenant ON evidence(tenant_id, evidence_id);
                CREATE TABLE IF NOT EXISTS calculations(
                    calculation_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, formula_id TEXT NOT NULL,
                    formula_version TEXT NOT NULL, inputs_json TEXT NOT NULL, output_value TEXT NOT NULL,
                    output_unit TEXT, evidence_ids_json TEXT NOT NULL, reproducibility_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_calculations_tenant ON calculations(tenant_id, calculation_id);
                CREATE TABLE IF NOT EXISTS deadlines(
                    deadline_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, due_date TEXT NOT NULL,
                    basis_evidence_ids_json TEXT NOT NULL, timezone_name TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_deadlines_tenant ON deadlines(tenant_id, deadline_id);
                CREATE TABLE IF NOT EXISTS findings(
                    finding_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, finding_type TEXT NOT NULL,
                    state TEXT NOT NULL, evidence_ids_json TEXT NOT NULL, calculation_ids_json TEXT NOT NULL,
                    reviewer TEXT, decision_reason TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_findings_tenant ON findings(tenant_id, finding_id);
                CREATE TABLE IF NOT EXISTS audit_events(
                    event_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, actor_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, subject_ref TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL, payload_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_events(tenant_id, event_id);
                CREATE TABLE IF NOT EXISTS notification_outbox(
                    event_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, event_type TEXT NOT NULL,
                    subject_ref TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL, delivered_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_outbox_tenant ON notification_outbox(tenant_id, event_id);
                """
            )
            conn.execute("INSERT OR REPLACE INTO assurance_meta(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))

    @staticmethod
    def _json(value) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    def put_evidence(self, item: EvidenceEnvelope) -> None:
        values = (item.evidence_id, item.tenant_id, item.source_type, item.source_ref, item.received_at, item.content_hash, self._json(item.metadata))
        with self._connect() as conn:
            existing = conn.execute("SELECT * FROM evidence WHERE evidence_id=?", (item.evidence_id,)).fetchone()
            if existing:
                current_semantic = tuple(existing[key] for key in ("evidence_id","tenant_id","source_type","source_ref","content_hash","metadata_json"))
                new_semantic = (item.evidence_id, item.tenant_id, item.source_type, item.source_ref, item.content_hash, self._json(item.metadata))
                if current_semantic != new_semantic:
                    raise AssuranceStoreError("immutable evidence id collision")
                return
            conn.execute("INSERT INTO evidence VALUES(?,?,?,?,?,?,?)", values)

    def put_calculation(self, item: CalculationRecord) -> None:
        inputs = [input_item.__dict__ for input_item in item.inputs]
        values = (item.calculation_id, item.tenant_id, item.formula_id, item.formula_version, self._json(inputs), item.output_value, item.output_unit, self._json(item.evidence_ids), item.reproducibility_hash)
        with self._connect() as conn:
            existing = conn.execute("SELECT * FROM calculations WHERE calculation_id=?", (item.calculation_id,)).fetchone()
            if existing:
                current = tuple(existing[key] for key in ("calculation_id","tenant_id","formula_id","formula_version","inputs_json","output_value","output_unit","evidence_ids_json","reproducibility_hash"))
                if current != values:
                    raise AssuranceStoreError("immutable calculation id collision")
                return
            conn.execute("INSERT INTO calculations VALUES(?,?,?,?,?,?,?,?,?)", values)

    def put_deadline(self, item: DeadlineWindow) -> None:
        values = (item.deadline_id, item.tenant_id, item.due_date.isoformat(), self._json(item.basis_evidence_ids), item.timezone_name)
        with self._connect() as conn:
            existing = conn.execute("SELECT * FROM deadlines WHERE deadline_id=?", (item.deadline_id,)).fetchone()
            if existing:
                current = tuple(existing[key] for key in ("deadline_id","tenant_id","due_date","basis_evidence_ids_json","timezone_name"))
                if current != values:
                    raise AssuranceStoreError("immutable deadline id collision")
                return
            conn.execute("INSERT INTO deadlines VALUES(?,?,?,?,?)", values)

    def put_finding(self, item: FindingRecord) -> None:
        values = (item.finding_id, item.tenant_id, item.finding_type, item.state, self._json(item.evidence_ids), self._json(item.calculation_ids), item.reviewer, item.decision_reason)
        with self._connect() as conn:
            existing = conn.execute("SELECT tenant_id FROM findings WHERE finding_id=?", (item.finding_id,)).fetchone()
            if existing and existing["tenant_id"] != item.tenant_id:
                raise AssuranceStoreError("cross-tenant finding id collision")
            conn.execute(
                """INSERT INTO findings VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(finding_id) DO UPDATE SET
                   finding_type=excluded.finding_type, state=excluded.state,
                   evidence_ids_json=excluded.evidence_ids_json,
                   calculation_ids_json=excluded.calculation_ids_json,
                   reviewer=excluded.reviewer, decision_reason=excluded.decision_reason""", values,
            )

    def append_audit(self, event: AuditEvent) -> None:
        values = (event.event_id, event.tenant_id, event.actor_id, event.event_type, event.occurred_at, event.subject_ref, self._json(event.evidence_refs), event.payload_hash)
        with self._connect() as conn:
            existing = conn.execute("SELECT * FROM audit_events WHERE event_id=?", (event.event_id,)).fetchone()
            if existing:
                current_semantic = tuple(existing[key] for key in ("event_id","tenant_id","actor_id","event_type","subject_ref","evidence_refs_json","payload_hash"))
                new_semantic = (event.event_id, event.tenant_id, event.actor_id, event.event_type, event.subject_ref, self._json(event.evidence_refs), event.payload_hash)
                if current_semantic != new_semantic:
                    raise AssuranceStoreError("immutable audit event id collision")
                return
            conn.execute("INSERT INTO audit_events VALUES(?,?,?,?,?,?,?,?)", values)

    def enqueue_notification(self, event: NotificationEvent) -> bool:
        values = (event.event_id, event.tenant_id, event.event_type, event.subject_ref, event.idempotency_key, self._json(event.payload), None)
        with self._connect() as conn:
            existing = conn.execute("SELECT * FROM notification_outbox WHERE idempotency_key=?", (event.idempotency_key,)).fetchone()
            if existing:
                comparable = tuple(existing[key] for key in ("event_id","tenant_id","event_type","subject_ref","idempotency_key","payload_json"))
                if comparable != values[:-1]:
                    raise AssuranceStoreError("notification idempotency collision")
                return False
            conn.execute("INSERT INTO notification_outbox VALUES(?,?,?,?,?,?,?)", values)
            return True

    def persist_case(self, *, evidence: Iterable[EvidenceEnvelope], calculation: CalculationRecord, deadline: DeadlineWindow, finding: FindingRecord, audit: AuditEvent, notification: NotificationEvent) -> None:
        tenant_ids = {calculation.tenant_id, deadline.tenant_id, finding.tenant_id, audit.tenant_id, notification.tenant_id}
        evidence_items = tuple(evidence)
        tenant_ids.update(item.tenant_id for item in evidence_items)
        if len(tenant_ids) != 1:
            raise AssuranceStoreError("cross-tenant case persistence rejected")
        for item in evidence_items:
            self.put_evidence(item)
        self.put_calculation(calculation)
        self.put_deadline(deadline)
        self.put_finding(finding)
        self.append_audit(audit)
        self.enqueue_notification(notification)

    def count(self, table: str, tenant_id: str) -> int:
        allowed = {"evidence", "calculations", "deadlines", "findings", "audit_events", "notification_outbox"}
        if table not in allowed:
            raise AssuranceStoreError("unsupported table")
        with self._connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE tenant_id=?", (tenant_id,)).fetchone()
        return int(row["n"])
