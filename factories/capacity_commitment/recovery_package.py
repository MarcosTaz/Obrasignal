from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .engine import RecoveryCase, RecoveryResult, RecoverabilityState


@dataclass(frozen=True)
class RecoveryPackage:
    case_id: str
    executive_summary: dict
    commitment_baseline: dict
    actual_consumption: dict
    shortfall: dict
    dedicated_capacity: dict
    investment_exposure: dict
    mitigation: dict
    contractual_basis: dict
    recoverability: dict
    evidence: Tuple[str, ...]
    missing_evidence: Tuple[str, ...]
    deadline: Optional[str]
    next_actions: Tuple[str, ...]
    audit_trail: dict


def _next_actions(result: RecoveryResult, missing_evidence: Tuple[str, ...]) -> Tuple[str, ...]:
    if result.recoverability_state is RecoverabilityState.RECOVERABLE:
        return (
            "prepare_evidence_supported_commercial_recovery_package",
            "obtain_authorized_human_review_before_external_submission",
        )
    if result.recoverability_state is RecoverabilityState.UNKNOWN:
        actions = ["do_not_present_as_recoverable"]
        if missing_evidence:
            actions.append("resolve_missing_evidence")
        actions.append("resolve_unknown_or_conflicting_basis")
        return tuple(actions)
    if result.recoverability_state is RecoverabilityState.EXPIRED:
        return ("do_not_present_as_claimable", "record_expiry_and_preserve_audit_trail")
    if result.recoverability_state is RecoverabilityState.NON_RECOVERABLE:
        return ("do_not_present_as_recoverable", "record_non_recoverable_basis")
    return ("close_or_monitor_zero_exposure",)


def build_recovery_package(
    case: RecoveryCase,
    result: RecoveryResult,
    *,
    evidence_refs: Tuple[str, ...] = (),
    missing_evidence: Tuple[str, ...] = (),
    deadline: Optional[str] = None,
) -> RecoveryPackage:
    """Build a truth-preserving assisted-review package.

    This function never upgrades the evaluator's truth state and never invents
    evidence, deadlines, contractual rights, approvals, settlements, or payment.
    """

    if result.case_id != case.case_id:
        raise ValueError("result does not belong to case")

    state = result.recoverability_state
    positive_position = state is RecoverabilityState.RECOVERABLE

    executive_summary = {
        "currency": result.currency,
        "economic_exposure": result.economic_exposure,
        "net_exposure": result.net_exposure,
        "recoverability_state": state.value,
        "recoverable_amount": result.recoverable_amount,
        "claimable_amount": result.claimable_amount,
        "verified_recovery": False,
        "payment_received": False,
    }

    commitment_baseline = {
        "commitment_state": case.commitment_state.value,
        "committed_units": case.committed_units,
        "customer_matches": case.customer_matches,
        "explicit_recovery_right": case.explicit_recovery_right,
        "contract_matches": case.contract_matches,
        "contract_current": case.contract_current,
        "amendment_reviewed": case.amendment_reviewed,
        "amendment_matches": case.amendment_matches,
    }

    actual_consumption = {
        "actual_units": case.actual_units,
        "unit_matches": case.unit_matches,
        "actuals_complete": case.actuals_complete,
        "actuals_deduplicated": case.actuals_deduplicated,
        "cancelled_orders_excluded": case.cancelled_orders_excluded,
    }
    shortfall = {"shortfall_units": result.shortfall_units}
    dedicated_capacity = {
        "asset_dedicated": case.asset_dedicated,
        "asset_dedication_verified": case.asset_dedication_verified,
        "exposure_type": case.exposure_type.value,
        "amortization_basis_units": case.amortization_basis_units,
        "amortization_verified": case.amortization_verified,
    }
    investment_exposure = {
        "exposure_type": case.exposure_type.value,
        "cost_recovery_mode": case.cost_recovery_mode.value,
        "dedicated_cost": case.dedicated_cost,
        "amortization_basis_units": case.amortization_basis_units,
        "amortization_verified": case.amortization_verified,
        "recovered_via_actual_units": result.recovered_via_actual_units,
        "economic_exposure": result.economic_exposure,
        "net_exposure": result.net_exposure,
    }
    mitigation = {
        "mitigation": result.mitigation,
        "mitigation_reviewed": case.mitigation_reviewed,
        "prior_payment": result.prior_payment,
        "prior_recovery_reviewed": case.prior_recovery_reviewed,
    }
    contractual_basis = {
        "customer_matches": case.customer_matches,
        "explicit_recovery_right": case.explicit_recovery_right,
        "program_matches": case.program_matches,
        "period_matches": case.period_matches,
        "currency_matches": case.currency_matches,
        "unit_matches": case.unit_matches,
        "amortization_verified": case.amortization_verified,
        "asset_dedication_verified": case.asset_dedication_verified,
        "mitigation_reviewed": case.mitigation_reviewed,
        "prior_recovery_reviewed": case.prior_recovery_reviewed,
        "notice_window_verified": case.notice_window_verified,
        "contract_matches": case.contract_matches,
        "contract_current": case.contract_current,
        "amendment_reviewed": case.amendment_reviewed,
        "amendment_matches": case.amendment_matches,
        "asset_dedicated": case.asset_dedicated,
        "evidence_supported": case.evidence_supported,
        "notice_valid": case.notice_valid,
        "duplicate_claim": case.duplicate_claim,
    }
    recoverability = {
        "state": state.value,
        "recoverable_amount": result.recoverable_amount,
        "claimable_amount": result.claimable_amount,
        "positive_position": positive_position,
        "reasons": result.reasons,
    }
    audit_trail = {
        "case_id": case.case_id,
        "engine_version": result.engine_version,
        "source_evidence_refs": evidence_refs,
        "missing_evidence": missing_evidence,
        "deadline": deadline,
        "customer_matches": case.customer_matches,
        "contract_matches": case.contract_matches,
        "amendment_matches": case.amendment_matches,
        "asset_dedication_verified": case.asset_dedication_verified,
        "mitigation_reviewed": case.mitigation_reviewed,
        "prior_recovery_reviewed": case.prior_recovery_reviewed,
        "notice_window_verified": case.notice_window_verified,
        "engine_reasons": result.reasons,
        "human_review_required_before_external_submission": positive_position,
    }

    return RecoveryPackage(
        case_id=case.case_id,
        executive_summary=executive_summary,
        commitment_baseline=commitment_baseline,
        actual_consumption=actual_consumption,
        shortfall=shortfall,
        dedicated_capacity=dedicated_capacity,
        investment_exposure=investment_exposure,
        mitigation=mitigation,
        contractual_basis=contractual_basis,
        recoverability=recoverability,
        evidence=evidence_refs,
        missing_evidence=missing_evidence,
        deadline=deadline,
        next_actions=_next_actions(result, missing_evidence),
        audit_trail=audit_trail,
    )
