from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional, Tuple


ZERO = Decimal("0")


class CommitmentState(str, Enum):
    FIRM = "FIRM"
    FORECAST_ONLY = "FORECAST_ONLY"
    AMBIGUOUS = "AMBIGUOUS"
    NONE = "NONE"


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
    if case.dedicated_cost > ZERO and case.amortization_basis_units <= ZERO:
        raise ValueError("amortization_basis_units must be positive when dedicated_cost is positive")
    if not case.currency or len(case.currency) != 3:
        raise ValueError("currency must be a 3-letter code")


def evaluate_recoverability(case: RecoveryCase) -> RecoveryResult:
    """Evaluate a single dedicated-investment/volume-shortfall case.

    Truth discipline:
    - economic exposure is calculated independently of legal/commercial entitlement;
    - a forecast-only or ambiguous volume is never promoted into a firm commitment;
    - mitigation and prior payments reduce the amount before any recoverability result;
    - unknown evidence/right/notice states fail closed to zero claimable amount.
    """

    _validate(case)

    shortfall_units = max(case.committed_units - case.actual_units, ZERO)
    unit_amortization = (
        case.dedicated_cost / case.amortization_basis_units
        if case.amortization_basis_units > ZERO
        else ZERO
    )
    recovered_via_actual_units = min(
        case.dedicated_cost,
        min(case.actual_units, case.amortization_basis_units) * unit_amortization,
    )

    if case.already_fully_amortized:
        economic_exposure = ZERO
    else:
        economic_exposure = max(case.dedicated_cost - recovered_via_actual_units, ZERO)

    net_exposure = max(
        economic_exposure - case.mitigation - case.prior_payment,
        ZERO,
    )

    reasons = []

    if net_exposure == ZERO:
        state = RecoverabilityState.ZERO_EXPOSURE
        recoverable = ZERO
        claimable = ZERO
        reasons.append("no_net_exposure_remaining")
    elif not case.asset_dedicated:
        state = RecoverabilityState.NON_RECOVERABLE
        recoverable = ZERO
        claimable = ZERO
        reasons.append("asset_not_proven_dedicated")
    elif case.commitment_state is CommitmentState.FORECAST_ONLY:
        state = RecoverabilityState.NON_RECOVERABLE
        recoverable = ZERO
        claimable = ZERO
        reasons.append("forecast_is_not_firm_commitment")
    elif case.commitment_state is CommitmentState.NONE:
        state = RecoverabilityState.NON_RECOVERABLE
        recoverable = ZERO
        claimable = ZERO
        reasons.append("no_customer_commitment")
    elif case.commitment_state is CommitmentState.AMBIGUOUS:
        state = RecoverabilityState.UNKNOWN
        recoverable = ZERO
        claimable = ZERO
        reasons.append("commitment_ambiguous")
    elif case.explicit_recovery_right is False:
        state = RecoverabilityState.NON_RECOVERABLE
        recoverable = ZERO
        claimable = ZERO
        reasons.append("recovery_right_not_supported")
    elif case.explicit_recovery_right is None:
        state = RecoverabilityState.UNKNOWN
        recoverable = ZERO
        claimable = ZERO
        reasons.append("recovery_right_unknown")
    elif not case.evidence_supported:
        state = RecoverabilityState.UNKNOWN
        recoverable = ZERO
        claimable = ZERO
        reasons.append("evidence_incomplete")
    elif case.notice_valid is False:
        state = RecoverabilityState.EXPIRED
        recoverable = ZERO
        claimable = ZERO
        reasons.append("notice_or_deadline_expired")
    elif case.notice_valid is None:
        state = RecoverabilityState.UNKNOWN
        recoverable = ZERO
        claimable = ZERO
        reasons.append("notice_validity_unknown")
    else:
        state = RecoverabilityState.RECOVERABLE
        recoverable = net_exposure
        claimable = net_exposure
        reasons.append("firm_commitment_right_evidence_and_notice_supported")

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
