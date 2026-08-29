from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SEVERITIES = {"P0", "P1", "P2", "P3"}
ACK_TARGET_MINUTES = {"P0": 15, "P1": 60, "P2": 240, "P3": 480}
TRANSITIONS = {
    "OPEN": {"ACKNOWLEDGED"},
    "ACKNOWLEDGED": {"INVESTIGATING", "ESCALATED"},
    "INVESTIGATING": {"ESCALATED", "MITIGATED"},
    "ESCALATED": {"INVESTIGATING", "MITIGATED"},
    "MITIGATED": {"RESOLVED", "INVESTIGATING"},
    "RESOLVED": set(),
}


class SupportContinuityError(RuntimeError):
    pass


@dataclass(frozen=True)
class SupportIncident:
    incident_id: str
    severity: str
    state: str
    owner_role: str
    opened_at: str
    acknowledged_at: str | None
    last_customer_update_at: str | None
    closure_evidence_hash: str | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SupportLedger:
    """Durable, app-local support continuity ledger without raw customer messages."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS support_incidents(
                    incident_id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    state TEXT NOT NULL,
                    owner_role TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    acknowledged_at TEXT,
                    last_customer_update_at TEXT,
                    closure_evidence_hash TEXT
                );
                CREATE TABLE IF NOT EXISTS support_events(
                    event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    evidence_hash TEXT,
                    FOREIGN KEY(incident_id) REFERENCES support_incidents(incident_id)
                );
                CREATE INDEX IF NOT EXISTS idx_support_events_incident ON support_events(incident_id,event_seq);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _incident(row: sqlite3.Row) -> SupportIncident:
        return SupportIncident(
            incident_id=row["incident_id"], severity=row["severity"], state=row["state"],
            owner_role=row["owner_role"], opened_at=row["opened_at"],
            acknowledged_at=row["acknowledged_at"],
            last_customer_update_at=row["last_customer_update_at"],
            closure_evidence_hash=row["closure_evidence_hash"],
        )

    def open(self, *, incident_id: str, severity: str, owner_role: str, summary: str) -> SupportIncident:
        incident_id = incident_id.strip()
        owner_role = owner_role.strip()
        summary = summary.strip()
        if not incident_id or not owner_role or not summary:
            raise SupportContinuityError("incident id, owner role and summary are required")
        if severity not in SEVERITIES:
            raise SupportContinuityError("invalid support severity")
        now = _utc_now()
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM support_incidents WHERE incident_id=?", (incident_id,)).fetchone():
                raise SupportContinuityError("support incident id already exists")
            conn.execute(
                "INSERT INTO support_incidents VALUES(?,?,?,?,?,?,?,?)",
                (incident_id, severity, "OPEN", owner_role, now, None, None, None),
            )
            conn.execute(
                "INSERT INTO support_events(incident_id,event_type,occurred_at,evidence_hash) VALUES(?,?,?,?)",
                (incident_id, "OPENED", now, _hash(summary)),
            )
        return self.get(incident_id)

    def get(self, incident_id: str) -> SupportIncident:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM support_incidents WHERE incident_id=?", (incident_id,)).fetchone()
        if not row:
            raise SupportContinuityError("support incident not found")
        return self._incident(row)

    def transition(self, incident_id: str, target: str, *, evidence_ref: str | None = None) -> SupportIncident:
        current = self.get(incident_id)
        target = target.strip().upper()
        if target not in TRANSITIONS.get(current.state, set()):
            raise SupportContinuityError(f"invalid support transition {current.state}->{target}")
        now = _utc_now()
        acknowledged_at = current.acknowledged_at
        closure_hash = current.closure_evidence_hash
        if target == "ACKNOWLEDGED" and acknowledged_at is None:
            acknowledged_at = now
        if target == "RESOLVED":
            if current.last_customer_update_at is None:
                raise SupportContinuityError("resolution requires recorded customer update")
            if not str(evidence_ref or "").strip():
                raise SupportContinuityError("resolution requires closure evidence")
            closure_hash = _hash(str(evidence_ref))
        evidence_hash = _hash(str(evidence_ref)) if str(evidence_ref or "").strip() else None
        with self._connect() as conn:
            conn.execute(
                "UPDATE support_incidents SET state=?,acknowledged_at=?,closure_evidence_hash=? WHERE incident_id=?",
                (target, acknowledged_at, closure_hash, incident_id),
            )
            conn.execute(
                "INSERT INTO support_events(incident_id,event_type,occurred_at,evidence_hash) VALUES(?,?,?,?)",
                (incident_id, f"STATE:{target}", now, evidence_hash),
            )
        return self.get(incident_id)

    def record_customer_update(self, incident_id: str, *, communication_evidence_ref: str) -> SupportIncident:
        self.get(incident_id)
        ref = communication_evidence_ref.strip()
        if not ref:
            raise SupportContinuityError("communication evidence required")
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE support_incidents SET last_customer_update_at=? WHERE incident_id=?",
                (now, incident_id),
            )
            conn.execute(
                "INSERT INTO support_events(incident_id,event_type,occurred_at,evidence_hash) VALUES(?,?,?,?)",
                (incident_id, "CUSTOMER_UPDATE_RECORDED", now, _hash(ref)),
            )
        return self.get(incident_id)

    def acknowledgement_target_minutes(self, incident_id: str) -> int:
        return ACK_TARGET_MINUTES[self.get(incident_id).severity]

    def event_count(self, incident_id: str) -> int:
        self.get(incident_id)
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM support_events WHERE incident_id=?", (incident_id,)).fetchone()[0])
