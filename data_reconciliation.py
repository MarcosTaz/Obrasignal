"""Fail-closed reconciliation planning for integrity findings.

Plans are observational contracts only. They never execute a repair, select a
production record, or override a domain owner. A known repair direction is not the
same thing as an authorized or idempotent repair primitive.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from data_integrity import IntegrityFinding


@dataclass(frozen=True)
class ReconciliationPlan:
    invariant: str
    authoritative_side: str
    repair_direction: str
    automatic: bool
    blocker: str | None
    owner: str
    convergence_requirement: str

    def as_dict(self) -> dict:
        return asdict(self)


def plan_reconciliation(finding: IntegrityFinding) -> ReconciliationPlan:
    """Return a deterministic non-mutating plan for one integrity finding."""
    if finding.invariant == "PROFILE_READY_EVENT_MISSING":
        return ReconciliationPlan(
            invariant=finding.invariant,
            authoritative_side="company_profiles canonical profile existence",
            repair_direction=(
                "company_profiles -> Evaluation-owned profile_ready evidence/projection"
            ),
            automatic=False,
            blocker="OWNER_IDEMPOTENT_EVENT_REPLAY_REQUIRED",
            owner="Evaluation",
            convergence_requirement=(
                "repair once, repair twice, and repair after restart must produce the same "
                "logical lifecycle state without duplicate logical evidence"
            ),
        )

    return ReconciliationPlan(
        invariant=finding.invariant,
        authoritative_side="UNKNOWN",
        repair_direction="NONE_FAIL_CLOSED",
        automatic=False,
        blocker="UNKNOWN_AUTHORITY_OR_REPAIR_POLICY",
        owner=finding.owner,
        convergence_requirement=(
            "owner must define authoritative side, idempotency and stable convergence before repair"
        ),
    )


def report_plan_json(plan: ReconciliationPlan) -> str:
    """Machine-readable deterministic reconciliation evidence."""
    return json.dumps(plan.as_dict(), sort_keys=True, separators=(",", ":"))
