from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class FindingAdjudicationError(RuntimeError):
    pass


@dataclass(frozen=True)
class FindingAdjudication:
    tenant_id: str
    finding_id: str
    vertical: str
    entitlement_state: str
    breach_state: str
    adjudicator: str | None
    adjudicated_at: str | None
    decision_evidence_hash: str | None
    decision_reason_hash: str | None

    @property
    def actionable(self) -> bool:
        if self.entitlement_state != "ESTABLISHED":
            return False
        if self.breach_state not in {"NOT_APPLICABLE", "ESTABLISHED"}:
            return False
        return self.decision_evidence_hash is not None and self.adjudicator is not None


class FindingAdjudicationLedger:
    """Durable pre-action truth gate for evidence-backed/shadow findings.

    The ledger stores only hashes of decision evidence/reason. A shadow finding is
    registered UNKNOWN and cannot be approved/actioned until an explicit human
    adjudication establishes the required dimensions with evidence.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS finding_adjudications(
                    tenant_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    vertical TEXT NOT NULL,
                    entitlement_state TEXT NOT NULL,
                    breach_state TEXT NOT NULL,
                    adjudicator TEXT,
                    adjudicated_at TEXT,
                    decision_evidence_hash TEXT,
                    decision_reason_hash TEXT,
                    PRIMARY KEY(tenant_id,finding_id)
                );
                CREATE INDEX IF NOT EXISTS idx_finding_adjudication_vertical
                    ON finding_adjudications(vertical,tenant_id,finding_id);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _row(row: sqlite3.Row) -> FindingAdjudication:
        return FindingAdjudication(**dict(row))

    def register_shadow(
        self, *, tenant_id: str, finding_id: str, vertical: str, requires_breach: bool,
    ) -> FindingAdjudication:
        tenant_id = tenant_id.strip()
        finding_id = finding_id.strip()
        vertical = vertical.strip()
        if not tenant_id or not finding_id or not vertical:
            raise FindingAdjudicationError("tenant, finding and vertical are required")
        breach_state = "NOT_ESTABLISHED" if requires_breach else "NOT_APPLICABLE"
        values = (tenant_id, finding_id, vertical, "UNKNOWN", breach_state, None, None, None, None)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM finding_adjudications WHERE tenant_id=? AND finding_id=?",
                (tenant_id, finding_id),
            ).fetchone()
            if existing:
                current = self._row(existing)
                if current.vertical != vertical:
                    raise FindingAdjudicationError("finding adjudication vertical collision")
                return current
            conn.execute("INSERT INTO finding_adjudications VALUES(?,?,?,?,?,?,?,?,?)", values)
        return self.get(tenant_id=tenant_id, finding_id=finding_id)

    def get(self, *, tenant_id: str, finding_id: str) -> FindingAdjudication:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM finding_adjudications WHERE tenant_id=? AND finding_id=?",
                (tenant_id.strip(), finding_id.strip()),
            ).fetchone()
        if not row:
            raise FindingAdjudicationError("tenant-scoped adjudication not found")
        return self._row(row)

    def exists(self, *, tenant_id: str, finding_id: str) -> bool:
        with self._connect() as conn:
            return conn.execute(
                "SELECT 1 FROM finding_adjudications WHERE tenant_id=? AND finding_id=?",
                (tenant_id.strip(), finding_id.strip()),
            ).fetchone() is not None

    def adjudicate(
        self, *, tenant_id: str, finding_id: str, adjudicator: str,
        entitlement_established: bool, breach_established: bool | None,
        evidence_ref: str, reason: str,
    ) -> FindingAdjudication:
        current = self.get(tenant_id=tenant_id, finding_id=finding_id)
        adjudicator = adjudicator.strip()
        evidence_ref = evidence_ref.strip()
        reason = reason.strip()
        if not adjudicator or not evidence_ref or not reason:
            raise FindingAdjudicationError("adjudicator, decision evidence and reason are required")
        if not isinstance(entitlement_established, bool):
            raise FindingAdjudicationError("entitlement_established must be boolean")
        if current.breach_state == "NOT_APPLICABLE":
            if breach_established is not None:
                raise FindingAdjudicationError("breach decision is not applicable to this vertical")
            breach_state = "NOT_APPLICABLE"
        else:
            if not isinstance(breach_established, bool):
                raise FindingAdjudicationError("breach_established must be boolean for this vertical")
            breach_state = "ESTABLISHED" if breach_established else "NOT_ESTABLISHED"
        entitlement_state = "ESTABLISHED" if entitlement_established else "NOT_ESTABLISHED"
        adjudicated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """UPDATE finding_adjudications
                   SET entitlement_state=?,breach_state=?,adjudicator=?,adjudicated_at=?,
                       decision_evidence_hash=?,decision_reason_hash=?
                   WHERE tenant_id=? AND finding_id=?""",
                (
                    entitlement_state, breach_state, adjudicator, adjudicated_at,
                    self._hash(evidence_ref), self._hash(reason), current.tenant_id, current.finding_id,
                ),
            )
        return self.get(tenant_id=current.tenant_id, finding_id=current.finding_id)

    def require_actionable(self, *, tenant_id: str, finding_id: str) -> FindingAdjudication:
        decision = self.get(tenant_id=tenant_id, finding_id=finding_id)
        if not decision.actionable:
            raise FindingAdjudicationError(
                "shadow finding is not actionably adjudicated: entitlement/breach evidence remains unresolved"
            )
        return decision
