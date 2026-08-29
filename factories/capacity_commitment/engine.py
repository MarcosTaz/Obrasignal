from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from enum import Enum
from typing import Optional, Tuple


ZERO = Decimal("0")
ENGINE_VERSION = "capacity-recoverability-t1.10"
ENGINE_DECIMAL_PRECISION = 60
ENGINE_DECIMAL_EMAX = 999999
ENGINE_DECIMAL_EMIN = -999999


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
    customer_matches: Optional[bool] = None
    program_matches: Optional[bool] = None
    period_matches: Optional[bool] = None
    currency_matches: Optional[bool] = None
    unit_matches: Optional[bool] = None
    actuals_complete: Optional[bool] = None
    actuals_deduplicated: Optional[bool] = None
    cancelled_orders_excluded: Optional[bool] = None
    amortization_verified: Optional[bool] = None
    asset_dedication_verified: Optional[bool] = None
    mitigation_reviewed: Optional[bool] = None
    prior_recovery_reviewed: Optional[bool] = None
    notice_window_verified: Optional[bool] = None
    contract_matches: Optional[bool] = None
    contract_current: Optional[bool] = None
    amendment_reviewed: Optional[bool] = None
    amendment_matches: Optional[bool] = None
    duplicate_claim: bool = False


@dataclass(frozen=True)
class RecoveryResult:
    engine_version: str
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


def _engine_decimal_context() -> Context:
    """Return a fresh arithmetic context so caller/global Decimal state is irrelevant."""

    return Context(
        prec=ENGINE_DECIMAL_PRECISION,
        rounding=ROUND_HALF_EVEN,
        Emin=ENGINE_DECIMAL_EMIN,
        Emax=ENGINE_DECIMAL_EMAX,
    )


def _validate(case: RecoveryCase) -> None:
    if not isinstance(case.case_id, str) or not case.case_id.strip() or len(case.case_id) > 200:
        raise ValueError("case_id must be a non-empty string up to 200 characters")
    if (
        not isinstance(case.currency, str)
        or len(case.currency) != 3
        or not case.currency.isascii()
        or not case.currency.isalpha()
    ):
        raise ValueError("currency must be a 3-letter ASCII alphabetic code")
    if not isinstance(case.commitment_state, CommitmentState):
        raise ValueError("commitment_state must be a valid CommitmentState")
    if not isinstance(case.exposure_type, ExposureType):
        raise ValueError("exposure_type must be a valid ExposureType")
    if not isinstance(case.cost_recovery_mode, CostRecoveryMode):
        raise ValueError("cost_recovery_mode must be a valid CostRecoveryMode")

    numeric = {
        "committed_units": case.committed_units,
        "actual_units": case.actual_units,
        "dedicated_cost": case.dedicated_cost,
        "amortization_basis_units": case.amortization_basis_units,
        "mitigation": case.mitigation,
        "prior_payment": case.prior_payment,
    }
    for name, value in numeric.items():
        if not isinstance(value, Decimal):
            raise ValueError(f"{name} must be an exact Decimal value")
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        if value < ZERO:
            raise ValueError(f"{name} must be non-negative")

    required_bools = {
        "evidence_supported": case.evidence_supported,
        "asset_dedicated": case.asset_dedicated,
        "already_fully_amortized": case.already_fully_amortized,
        "already_paid": case.already_paid,
        "duplicate_claim": case.duplicate_claim,
    }
    for name, value in required_bools.items():
        if type(value) is not bool:
            raise ValueError(f"{name} must be boolean")

    optional_bools = {
        "explicit_recovery_right": case.explicit_recovery_right,
        "notice_valid": case.notice_valid,
        "customer_matches": case.customer_matches,
        "program_matches": case.program_matches,
        "period_matches": case.period_matches,
        "currency_matches": case.currency_matches,
        "unit_matches": case.unit_matches,
        "actuals_complete": case.actuals_complete,
        "actuals_deduplicated": case.actuals_deduplicated,
        "cancelled_orders_excluded": case.cancelled_orders_excluded,
        "amortization_verified": case.amortization_verified,
        "asset_dedication_verified": case.asset_dedication_verified,
        "mitigation_reviewed": case.mitigation_reviewed,
        "prior_recovery_reviewed": case.prior_recovery_reviewed,
        "notice_window_verified": case.notice_window_verified,
        "contract_matches": case.contract_matches,
        "contract_current": case.contract_current,
        "amendment_reviewed": case.amendment_reviewed,
        "amendment_matches": case.amendment_matches,
    }
    for name, value in optional_bools.items():
        if value is not None and type(value) is not bool:
            raise ValueError(f"{name} must be boolean or null")

    if (
        case.cost_recovery_mode is CostRecoveryMode.UNIT_AMORTIZED
        and case.dedicated_cost > ZERO
        and case.amortization_basis_units <= ZERO
    ):
        raise ValueError("amortization_basis_units must be positive for unit-amortized cost")


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


def _first_tri_state_failure(checks) -> Optional[tuple[RecoverabilityState, str]]:
    for value, unknown_reason, false_reason in checks:
        if value is None:
            return RecoverabilityState.UNKNOWN, unknown_reason
        if value is False:
            return RecoverabilityState.UNKNOWN, false_reason
    return None


def _zero_exposure_integrity_gate(
    case: RecoveryCase,
    economic_exposure: Decimal,
) -> Optional[tuple[RecoverabilityState, str]]:
    """Prevent an unverified input from being upgraded into a definitive zero.

    Entitlement-only evidence (notice, recovery right, contract wording) is not
    required to establish a structural economic zero. But when the zero depends
    on amortization/actuals, mitigation or prior recovery, the inputs that caused
    that zero must themselves be verified.
    """

    if case.dedicated_cost == ZERO:
        return None

    if case.already_fully_amortized:
        if case.amortization_verified is None:
            return RecoverabilityState.UNKNOWN, "amortization_verification_unknown"
        if case.amortization_verified is False:
            return RecoverabilityState.UNKNOWN, "amortization_basis_not_verified"
        return None

    if case.already_paid:
        if case.prior_recovery_reviewed is None:
            return RecoverabilityState.UNKNOWN, "prior_recovery_review_unknown"
        if case.prior_recovery_reviewed is False:
            return RecoverabilityState.UNKNOWN, "prior_recovery_not_reviewed"
        return None

    if (
        case.cost_recovery_mode is CostRecoveryMode.UNIT_AMORTIZED
        and economic_exposure == ZERO
    ):
        failure = _first_tri_state_failure(
            (
                (case.customer_matches, "customer_match_unknown", "wrong_customer"),
                (case.program_matches, "program_match_unknown", "wrong_program"),
                (case.period_matches, "period_match_unknown", "wrong_period"),
                (case.currency_matches, "currency_match_unknown", "wrong_currency"),
                (case.unit_matches, "unit_match_unknown", "wrong_unit"),
                (case.actuals_complete, "actuals_completeness_unknown", "actuals_incomplete"),
                (
                    case.actuals_deduplicated,
                    "actuals_deduplication_unknown",
                    "duplicate_volume",
                ),
                (
                    case.cancelled_orders_excluded,
                    "cancelled_order_reconciliation_unknown",
                    "cancelled_order_in_actuals",
                ),
                (
                    case.amortization_verified,
                    "amortization_verification_unknown",
                    "amortization_basis_not_verified",
                ),
            )
        )
        if failure is not None:
            return failure

    if case.mitigation > ZERO:
        if case.mitigation_reviewed is None:
            return RecoverabilityState.UNKNOWN, "mitigation_review_unknown"
        if case.mitigation_reviewed is False:
            return RecoverabilityState.UNKNOWN, "mitigation_not_reviewed"

    if case.prior_payment > ZERO:
        if case.prior_recovery_reviewed is None:
            return RecoverabilityState.UNKNOWN, "prior_recovery_review_unknown"
        if case.prior_recovery_reviewed is False:
            return RecoverabilityState.UNKNOWN, "prior_recovery_not_reviewed"

    return None


def _integrity_gate(case: RecoveryCase) -> Optional[tuple[RecoverabilityState, str]]:
    failure = _first_tri_state_failure(
        (
            (case.customer_matches, "customer_match_unknown", "wrong_customer"),
            (case.program_matches, "program_match_unknown", "wrong_program"),
            (case.period_matches, "period_match_unknown", "wrong_period"),
            (case.currency_matches, "currency_match_unknown", "wrong_currency"),
            (case.unit_matches, "unit_match_unknown", "wrong_unit"),
            (case.actuals_complete, "actuals_completeness_unknown", "actuals_incomplete"),
            (case.actuals_deduplicated, "actuals_deduplication_unknown", "duplicate_volume"),
            (
                case.cancelled_orders_excluded,
                "cancelled_order_reconciliation_unknown",
                "cancelled_order_in_actuals",
            ),
            (
                case.amortization_verified,
                "amortization_verification_unknown",
                "amortization_basis_not_verified",
            ),
            (case.mitigation_reviewed, "mitigation_review_unknown", "mitigation_not_reviewed"),
            (
                case.prior_recovery_reviewed,
                "prior_recovery_review_unknown",
                "prior_recovery_not_reviewed",
            ),
            (
                case.notice_window_verified,
                "notice_window_verification_unknown",
                "notice_window_not_verified",
            ),
            (case.contract_matches, "contract_match_unknown", "wrong_contract"),
            (case.contract_current, "contract_current_unknown", "superseded_contract"),
            (
                case.amendment_reviewed,
                "amendment_review_unknown",
                "customer_amendment_not_reconciled",
            ),
            (case.amendment_matches, "amendment_match_unknown", "wrong_amendment"),
        )
    )
    if failure is not None:
        return failure
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

    with localcontext(_engine_decimal_context()):
        shortfall_units = max(case.committed_units - case.actual_units, ZERO)
        unit_amortization, recovered_via_actual_units, economic_exposure = _economic_exposure(case)
        net_exposure = max(economic_exposure - case.mitigation - case.prior_payment, ZERO)

    reasons = []
    state: RecoverabilityState
    recoverable = ZERO
    claimable = ZERO

    if net_exposure == ZERO:
        zero_integrity = _zero_exposure_integrity_gate(case, economic_exposure)
        if zero_integrity is not None:
            state, reason = zero_integrity
            reasons.append(reason)
        else:
            state = RecoverabilityState.ZERO_EXPOSURE
            reasons.append("no_net_exposure_remaining")
    else:
        integrity = _integrity_gate(case)
        if integrity is not None:
            state, reason = integrity
            reasons.append(reason)
        elif case.exposure_type in {ExposureType.DEDICATED_CAPEX, ExposureType.TOOLING}:
            if case.asset_dedication_verified is None:
                state = RecoverabilityState.UNKNOWN
                reasons.append("asset_dedication_verification_unknown")
            elif case.asset_dedication_verified is False:
                state = RecoverabilityState.UNKNOWN
                reasons.append("asset_dedication_not_verified")
            elif not case.asset_dedicated:
                state = RecoverabilityState.NON_RECOVERABLE
                reasons.append("asset_not_proven_dedicated")
            else:
                state = None
        else:
            state = None

        if state is None:
            if (
                case.commitment_state in {CommitmentState.FIRM, CommitmentState.FLEX_WINDOW}
                and case.committed_units == ZERO
            ):
                state = RecoverabilityState.NON_RECOVERABLE
                reasons.append("zero_effective_commitment")
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
        engine_version=ENGINE_VERSION,
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
