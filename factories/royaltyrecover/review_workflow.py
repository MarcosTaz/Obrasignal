from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from recoverability_scan import ScanState
from royalty_engine import FindingState
from service_pipeline import EvidencePack


class ReviewDecision(str, Enum):
    REQUEST_MORE_DATA = "REQUEST_MORE_DATA"
    REJECT_RECOVERY = "REJECT_RECOVERY"
    APPROVE_DESK_FINDING = "APPROVE_DESK_FINDING"
    ROUTE_TO_FORMAL_AUDIT = "ROUTE_TO_FORMAL_AUDIT"
    REQUIRE_PROFESSIONAL_REVIEW = "REQUIRE_PROFESSIONAL_REVIEW"


class ReviewOutcome(str, Enum):
    BLOCKED = "BLOCKED"
    NO_RECOVERY = "NO_RECOVERY"
    DESK_FINDING_APPROVED = "DESK_FINDING_APPROVED"
    FORMAL_AUDIT_READY = "FORMAL_AUDIT_READY"
    PROFESSIONAL_REVIEW_REQUIRED = "PROFESSIONAL_REVIEW_REQUIRED"


@dataclass(frozen=True)
class HumanReview:
    reviewer_id: str
    reviewer_role: str
    decision: ReviewDecision
    rationale: str


@dataclass(frozen=True)
class ReviewedPack:
    case_id: str
    outcome: ReviewOutcome
    review: HumanReview
    claim_ready: bool
    formal_audit_ready: bool
    reason: str


def review_evidence_pack(pack: EvidencePack, review: HumanReview) -> ReviewedPack:
    if not review.reviewer_id.strip() or not review.reviewer_role.strip() or not review.rationale.strip():
        raise ValueError("reviewer identity, role and rationale are required")

    if review.decision == ReviewDecision.REQUEST_MORE_DATA:
        return ReviewedPack(
            pack.case_id, ReviewOutcome.BLOCKED, review, False, False,
            "Reviewer requested additional evidence; no recovery assertion is permitted.",
        )

    if review.decision == ReviewDecision.REJECT_RECOVERY:
        return ReviewedPack(
            pack.case_id, ReviewOutcome.NO_RECOVERY, review, False, False,
            "Reviewer rejected the recovery candidate; no claim is permitted.",
        )

    if review.decision == ReviewDecision.REQUIRE_PROFESSIONAL_REVIEW:
        return ReviewedPack(
            pack.case_id, ReviewOutcome.PROFESSIONAL_REVIEW_REQUIRED, review, False, False,
            "Professional contract/accounting/legal review is required before further action.",
        )

    if pack.calculation.state != FindingState.RECOVERY_CANDIDATE:
        return ReviewedPack(
            pack.case_id, ReviewOutcome.BLOCKED, review, False, False,
            "A positive deterministic recovery candidate is required before approval or formal-audit routing.",
        )

    if pack.information_requests:
        return ReviewedPack(
            pack.case_id, ReviewOutcome.BLOCKED, review, False, False,
            "Outstanding information requests must be resolved before approval or formal-audit routing.",
        )

    if review.decision == ReviewDecision.APPROVE_DESK_FINDING:
        if pack.scan.state == ScanState.FORMAL_AUDIT_CANDIDATE:
            return ReviewedPack(
                pack.case_id, ReviewOutcome.BLOCKED, review, False, False,
                "The agreement indicates a formal auditor requirement; desk approval cannot substitute for that route.",
            )
        return ReviewedPack(
            pack.case_id, ReviewOutcome.DESK_FINDING_APPROVED, review, False, False,
            "Desk finding is approved as an analytical finding only. It is still not a legal claim or formal audit conclusion.",
        )

    if review.decision == ReviewDecision.ROUTE_TO_FORMAL_AUDIT:
        return ReviewedPack(
            pack.case_id, ReviewOutcome.FORMAL_AUDIT_READY, review, False, True,
            "Evidence pack is ready to be routed to a qualified formal auditor; no claim has been asserted.",
        )

    return ReviewedPack(
        pack.case_id, ReviewOutcome.BLOCKED, review, False, False,
        "Unsupported review transition.",
    )
