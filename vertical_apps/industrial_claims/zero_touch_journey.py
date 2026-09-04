from __future__ import annotations

from dataclasses import dataclass


class ZeroTouchJourneyError(ValueError):
    pass


@dataclass(frozen=True)
class ZeroTouchJourneyInput:
    metadata_qualification: str = "UNASSESSED"
    account_created: bool = False
    case_metadata_complete: bool = False
    secure_intake_ready: bool = False
    evidence_uploaded: bool = False
    evidence_gap_count: int = 0
    verified_payment_state: str = "UNPAID"
    automated_analysis_complete: bool = False
    customer_confirmed_facts: bool = False
    dossier_ready: bool = False
    claim_workspace_enabled: bool = False
    portfolio_monitoring_enabled: bool = False


@dataclass(frozen=True)
class ZeroTouchJourneyResult:
    state: str
    next_action: str
    operator_intervention_required: bool
    confidential_upload_allowed: bool
    paid_access_granted: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "next_action": self.next_action,
            "operator_intervention_required": self.operator_intervention_required,
            "confidential_upload_allowed": self.confidential_upload_allowed,
            "paid_access_granted": self.paid_access_granted,
        }


def evaluate_zero_touch_journey(payload: ZeroTouchJourneyInput) -> ZeroTouchJourneyResult:
    """Return the next deterministic customer action without operator dependency.

    The normal VINDORUM path is zero-touch. Uncertainty is resolved by requesting
    missing customer evidence or confirmation, never by silently asserting a claim.
    Paid access is granted only from a server-verified ACTIVE billing projection.
    """
    if not isinstance(payload, ZeroTouchJourneyInput):
        raise ZeroTouchJourneyError("payload must be ZeroTouchJourneyInput")
    if not isinstance(payload.evidence_gap_count, int) or payload.evidence_gap_count < 0:
        raise ZeroTouchJourneyError("evidence_gap_count must be a non-negative integer")

    paid = payload.verified_payment_state == "ACTIVE"
    upload_allowed = bool(payload.secure_intake_ready)

    def result(state: str, action: str) -> ZeroTouchJourneyResult:
        return ZeroTouchJourneyResult(
            state=state,
            next_action=action,
            operator_intervention_required=False,
            confidential_upload_allowed=upload_allowed,
            paid_access_granted=paid,
        )

    if payload.metadata_qualification == "UNASSESSED":
        return result("TRIAGE_REQUIRED", "Complete the free exposure check.")
    if payload.metadata_qualification in {"NO_FIT", "WEAK_FIT"}:
        return result("NOT_A_FIT", "Keep the result and exit without purchasing a scan.")
    if not payload.account_created:
        return result("ACCOUNT_REQUIRED", "Create a VINDORUM account to save this case.")
    if not payload.case_metadata_complete:
        return result("CASE_METADATA_REQUIRED", "Complete customer, program, event and cost metadata.")
    if not payload.secure_intake_ready:
        return result("SECURE_INTAKE_BLOCKED", "Do not upload confidential evidence until secure intake is verified.")
    if not payload.evidence_uploaded:
        return result("EVIDENCE_REQUIRED", "Upload the available evidence through the authenticated case workspace.")
    if payload.evidence_gap_count:
        return result("EVIDENCE_GAPS", "Resolve the listed evidence gaps or mark unavailable items explicitly.")
    if not paid:
        return result("PAYMENT_REQUIRED", "Purchase the Recovery Scan; access unlocks only after verified payment.")
    if not payload.automated_analysis_complete:
        return result("ANALYSIS_PENDING", "Run automated evidence, causation and economic reconciliation.")
    if not payload.customer_confirmed_facts:
        return result("CUSTOMER_CONFIRMATION_REQUIRED", "Confirm extracted facts, amounts and unresolved assumptions.")
    if not payload.dossier_ready:
        return result("DOSSIER_PENDING", "Generate the evidence-linked Recovery Dossier.")
    if not payload.claim_workspace_enabled:
        return result("DOSSIER_READY", "Open the claim workspace from the completed dossier.")
    if payload.portfolio_monitoring_enabled:
        return result("PORTFOLIO_MONITORING", "Monitor new change-cost leakage and settlement state automatically.")
    return result("CLAIM_WORKSPACE", "Track claimed, approved and settled amounts; enable portfolio monitoring when needed.")
