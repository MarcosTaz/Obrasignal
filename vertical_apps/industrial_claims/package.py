from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from vertical_apps.industrial_claims.service import IndustrialClaimResult


def _notice_package(result: IndustrialClaimResult, *, as_of_date: date) -> dict[str, Any]:
    if result.notice_deadline_state == "DECLARED_DATE_FOR_REVIEW":
        timing_state = result.deadline.state_on(as_of_date)
        due_date = result.deadline.due_date.isoformat()
    elif result.notice_deadline_state == "DECLARED_NONE_FOR_REVIEW":
        timing_state = "NO_DEADLINE_DECLARED_FOR_REVIEW"
        due_date = None
    else:
        timing_state = "UNKNOWN"
        due_date = None
    return {
        "truth_state": result.notice_deadline_state,
        "due_date": due_date,
        "timing_state": timing_state,
        "as_of_date": as_of_date.isoformat(),
        "timing_establishes_recoverability": False,
        "expired_establishes_nonrecoverability": False,
        "expired_requires_human_exception_or_waiver_review": timing_state == "EXPIRED",
    }


def build_claim_package(
    result: IndustrialClaimResult,
    *,
    customer_ref: str,
    program_ref: str,
    event_ref: str,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """Build a review package without upgrading economic/legal truth state.

    The amount is deliberately labelled net_potential, never "owed" or
    "claimable". READY_FOR_REVIEW means documentary inputs are structurally
    present for independent human review; it does not establish entitlement or
    recoverability. Raw document content is not embedded.
    """
    as_of = as_of_date or date.today()
    currency = result.calculation.output_unit
    verified_currency = currency if currency and currency != "UNKNOWN" else None
    return {
        "schema_version": 5,
        "vertical": "industrial-claims",
        "tenant_id": result.tenant_id,
        "customer_ref": customer_ref,
        "program_ref": program_ref,
        "event_ref": event_ref,
        "claim_family": result.claim_family,
        "economic_truth_state": "DOCUMENTED_CANDIDATE_FOR_REVIEW" if result.finding.state == "READY_FOR_REVIEW" else "POTENTIAL_ENTITLEMENT",
        "net_potential": result.calculation.output_value,
        "currency": verified_currency,
        "calculation": {
            "formula_id": result.calculation.formula_id,
            "formula_version": result.calculation.formula_version,
            "reproducibility_hash": result.calculation.reproducibility_hash,
            "output_unit": result.calculation.output_unit,
            "inputs": [asdict(item) for item in result.calculation.inputs],
        },
        "entitlement": {
            "rule_ref": result.entitlement.rule_ref,
            "confidence": result.entitlement.confidence,
            "basis_hash": result.entitlement.basis_hash,
            "pre_review": True,
            "generic_actionable": False,
            "recoverability_established": False,
        },
        "notice": _notice_package(result, as_of_date=as_of),
        "evidence_index": [
            {
                "evidence_id": item.evidence_id,
                "source_type": item.source_type,
                "source_ref": item.source_ref,
                "content_hash": item.content_hash,
                "verification_state": item.metadata.get("verification_state", "UNKNOWN"),
                "raw_content_persisted": item.metadata.get("raw_content_persisted", "unknown"),
            }
            for item in result.evidence
        ],
        "missing_evidence": list(result.missing_evidence),
        "finding": {
            "finding_id": result.finding.finding_id,
            "state": result.finding.state,
            "workflow_scope": "DOCUMENTARY_REVIEW",
        },
        "duplicate_status": "NEW" if result.is_new_recovery else "REPLAY_OR_DUPLICATE",
        "customer_action_authorized": False,
        "external_claim_submission_authorized": False,
        "legal_conclusion": None,
    }
