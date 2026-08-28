from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, Tuple


ZERO = Decimal("0")


class CommitmentState(str, Enum):
    FIRM = "FIRM"
    FLEX_WINDOW = "FLEX_WINDOW"
    FORECAST_ONLY = "FORECAST_ONLY"
    AMBIGUOUS = "AMBIGUOUS"
    NONE = "NONE"


class ExposureType(str, Enum):
    DEDICATED_CAPEX = "DEDICATED_CAPEX"
    TOOLING = "TOOLING"
    NRE = "NRE"
    LABOR = "LABOR"
    MATERIAL = "MATERIAL"
    OTHER = "OTHER"


class CostRecoveryMode(str, Enum):
    UNIT_AMORTIZED = "UNIT_AMORTIZED"
    DIRECT_UNRECOVERED = "DIRECT_UNRECOVERED"


class RecoverabilityState(str, Enum):
    RECOVERABLE = "RECOVERABLE"
    NON_RECOVERABLE = "NON_RECOVERABLE"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"
    ZERO_EXPOSURE = "ZERO_EXPOSURE"


@dataclass(frozen=True)
class RecoveryCase:
    case_id: str
    currency: str
    committed_units: Decimal
    actual_units: Decimal
    dedicated_cost: Decimal
    amortization_basis_units: Decimal
    mitigation: Decimal = ZERO
    prior_payment: Decimal = ZERO
    commitment_state: CommitmentState = CommitmentState.AMBIGUOUS
    explicit_recovery_right: Optional[bool] = None
    evidence_supported: bool = False
    notice_valid: Optional[bool] = None
    asset_dedicated: bool = True
    already_fully_amortized: bool = False
    already_paid: bool = False
    exposure_type: ExposureType = ExposureType.DEDICATED_CAPEX
    cost_recovery_mode: CostRecoveryMode = CostRecoveryMode.UNIT_AMORTIZED
    program_matches: Optional[bool] = None
    period_matches: Optional[bool] = None
    currency_matches: Optional[bool] = None
    contract_current: Optional[bool] = None
    amendment_reviewed: Optional[bool] = None
    duplicate_claim: bool = False


@dataclass(frozen=True)
class RecoveryResult:
    case_id: str
    currency: str
    committed_units: Decimal
    actual_units: Decimal
    shortfall_units: Decimal
    unit_amortization: Decimal
    recovered_via_actual_units: Decimal
    economic_exposure: Decimal
    mitigation: Decimal
    prior_payment: Decimal
    net_exposure: Decimal
    recoverability_state: RecoverabilityState
    recoverable_amount: Decimal
    claimable_amount: Decimal
    reasons: Tuple[str, ...]


def _validate(case: RecoveryCase) -> None:
    numeric = {
        "committed_units": case.committed_units,
        "actual_units": case.actual_units,
        "dedicated_cost": case.dedicated_cost,
        "amortization_basis_units": case.amortization_basis_units,
        "mitigation": case.mitigation,
        "prior_payment": case.prior_payment,
    }
    for name, value in numeric.items():
        if value < ZERO:
            raise ValueError(f"{name} must be non-negative")
    if (
        case.cost_recovery_mode is CostRecoveryMode.UNIT_AMORTIZED
        and case.dedicated_cost > ZERO
        and case.amortization_basis_units <= ZERO
    ):
        raise ValueError("amortization_basis_units must be positive for unit-amortized cost")
    if not case.currency or len(case.currency) != 3 or not case.currency.isalpha():
        raise ValueError("currency must be a 3-letter alphabetic code")


def _economic_exposure(case: RecoveryCase) -> tuple[Decimal, Decimal, Decimal]:
    if case.already_fully_amortized or case.already_paid:
        return ZERO, ZERO, ZERO

    if case.cost_recovery_mode is CostRecoveryMode.DIRECT_UNRECOVERED:
        return ZERO, ZERO, case.dedicated_cost

    unit_amortization = (
        case.dedicated_cost / case.amortization_basis_units
        if case.amortization_basis_units > ZERO
        else ZERO
    )
    recovered_via_actual_units = min(
        case.dedicated_cost,
        min(case.actual_units, case.amortization_basis_units) * unit_amortization,
    )
    exposure = max(case.dedicated_cost - recovered_via_actual_units, ZERO)
    return unit_amortization, recovered_via_actual_units, exposure


def _integrity_gate(case: RecoveryCase) -> Optional[tuple[RecoverabilityState, str]]:
    checks = (
        (case.program_matches, "program_match_unknown", "wrong_program"),
        (case.period_matches, "period_match_unknown", "wrong_period"),
        (case.currency_matches, "currency_match_unknown", "wrong_currency"),
        (case.contract_current, "contract_current_unknown", "superseded_contract"),
        (case.amendment_reviewed, "amendment_review_unknown", "customer_amendment_not_reconciled"),
    )
    for value, unknown_reason, false_reason in checks:
        if value is None:
            return RecoverabilityState.UNKNOWN, unknown_reason
        if value is False:
            return RecoverabilityState.UNKNOWN, false_reason
    if case.duplicate_claim:
        return RecoverabilityState.NON_RECOVERABLE, "duplicate_claim"
    return None


def evaluate_recoverability(case: RecoveryCase) -> RecoveryResult:
    """Evaluate a single capacity/dedicated-investment recovery case.

    The evaluator deliberately separates economic exposure from entitlement.
    Unknown or contradictory contract/evidence/integrity states fail closed to
    zero claimable value; a correct zero is a successful result.
    """

    _validate(case)

    shortfall_units = max(case.committed_units - case.actual_units, ZERO)
    unit_amortization, recovered_via_actual_units, economic_exposure = _economic_exposure(case)
    net_exposure = max(economic_exposure - case.mitigation - case.prior_payment, ZERO)

    reasons = []
    state: RecoverabilityState
    recoverable = ZERO
    claimable = ZERO

    if net_exposure == ZERO:
        state = RecoverabilityState.ZERO_EXPOSURE
        reasons.append("no_net_exposure_remaining")
    else:
        integrity = _integrity_gate(case)
        if integrity is not None:
            state, reason = integrity
            reasons.append(reason)
        elif not case.asset_dedicated and case.exposure_type in {
            ExposureType.DEDICATED_CAPEX,
            ExposureType.TOOLING,
        }:
            state = RecoverabilityState.NON_RECOVERABLE
            reasons.append("asset_not_proven_dedicated")
        elif case.commitment_state is CommitmentState.FORECAST_ONLY:
            state = RecoverabilityState.NON_RECOVERABLE
            reasons.append("forecast_is_not_firm_commitment")
        elif case.commitment_state is CommitmentState.NONE:
            state = RecoverabilityState.NON_RECOVERABLE
            reasons.append("no_customer_commitment")
        elif case.commitment_state is CommitmentState.AMBIGUOUS:
            state = RecoverabilityState.UNKNOWN
            reasons.append("commitment_ambiguous")
        elif case.explicit_recovery_right is False:
            state = RecoverabilityState.NON_RECOVERABLE
            reasons.append("recovery_right_not_supported")
        elif case.explicit_recovery_right is None:
            state = RecoverabilityState.UNKNOWN
            reasons.append("recovery_right_unknown")
        elif not case.evidence_supported:
            state = RecoverabilityState.UNKNOWN
            reasons.append("evidence_incomplete")
        elif case.notice_valid is False:
            state = RecoverabilityState.EXPIRED
            reasons.append("notice_or_deadline_expired")
        elif case.notice_valid is None:
            state = RecoverabilityState.UNKNOWN
            reasons.append("notice_validity_unknown")
        else:
            state = RecoverabilityState.RECOVERABLE
            recoverable = net_exposure
            claimable = net_exposure
            reasons.append("commitment_right_evidence_integrity_and_notice_supported")

    return RecoveryResult(
        case_id=case.case_id,
        currency=case.currency.upper(),
        committed_units=case.committed_units,
        actual_units=case.actual_units,
        shortfall_units=shortfall_units,
        unit_amortization=unit_amortization,
        recovered_via_actual_units=recovered_via_actual_units,
        economic_exposure=economic_exposure,
        mitigation=case.mitigation,
        prior_payment=case.prior_payment,
        net_exposure=net_exposure,
        recoverability_state=state,
        recoverable_amount=recoverable,
        claimable_amount=claimable,
        reasons=tuple(reasons),
    )
