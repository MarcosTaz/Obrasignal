from __future__ import annotations

from dataclasses import asdict
from typing import Any

from vertical_apps.industrial_claims.service import IndustrialClaimResult


def build_claim_package(
    result: IndustrialClaimResult,
    *,
    customer_ref: str,
    program_ref: str,
    event_ref: str,
) -> dict[str, Any]:
    """Build a review package without upgrading economic/legal truth state.

    The amount is deliberately labelled net_potential, never "owed" or
    "claimable". Human review and customer authority remain external gates.
    """
    return {
        "schema_version": 1,
        "vertical": "industrial-claims",
        "tenant_id": result.tenant_id,
        "customer_ref": customer_ref,
        "program_ref": program_ref,
        "event_ref": event_ref,
        "claim_family": result.claim_family,
        "economic_truth_state": "EVIDENCE_SUPPORTED" if result.finding.state == "READY_FOR_REVIEW" else "POTENTIAL_ENTITLEMENT",
        "net_potential": result.calculation.output_value,
        "calculation": {
            "formula_id": result.calculation.formula_id,
            "formula_version": result.calculation.formula_version,
            "reproducibility_hash": result.calculation.reproducibility_hash,
            "inputs": [asdict(item) for item in result.calculation.inputs],
        },
        "entitlement": {
            "rule_ref": result.entitlement.rule_ref,
            "confidence": result.entitlement.confidence,
            "basis_hash": result.entitlement.basis_hash,
        },
        "evidence_index": [
            {
                "evidence_id": item.evidence_id,
                "source_type": item.source_type,
                "source_ref": item.source_ref,
                "content_hash": item.content_hash,
            }
            for item in result.evidence
        ],
        "missing_evidence": list(result.missing_evidence),
        "finding": {
            "finding_id": result.finding.finding_id,
            "state": result.finding.state,
        },
        "duplicate_status": "NEW" if result.is_new_recovery else "REPLAY_OR_DUPLICATE",
        "customer_action_authorized": False,
        "legal_conclusion": None,
    }
