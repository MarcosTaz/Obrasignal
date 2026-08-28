from decimal import Decimal

import pytest

from factories.capacity_commitment.engine import RecoveryCase, RecoverabilityState, evaluate_recoverability
from factories.capacity_commitment.synthetic_cases import CASES, case


MANDATORY_CASE_IDS = {
    "full-volume-delivered",
    "minor-shortfall",
    "major-shortfall",
    "program-delay",
    "program-cancellation",
    "partial-cancellation",
    "no-contractual-right",
    "strong-contractual-right",
    "ambiguous-commitment",
    "forecast-only-no-firm-commitment",
    "firm-window",
    "flex-window-effective-minimum",
    "dedicated-capex",
    "shared-capex",
    "tooling-fully-amortized",
    "tooling-partially-amortized",
    "nre-already-paid",
    "unused-labor-capacity",
    "material-reused",
    "material-scrapped",
    "mitigation-partial",
    "prior-customer-credit",
    "duplicate-claim",
    "wrong-program",
    "wrong-period",
    "wrong-currency",
    "superseded-contract",
    "customer-amendment-unreconciled",
    "expired-claim-right",
    "zero-recovery-right-unknown",
}

RED_TEAM_CASE_IDS = {
    "wrong-unit",
    "missing-call-off",
    "late-call-off-not-reconciled",
    "duplicate-volume",
    "cancelled-order-in-actuals",
    "wrong-amortization-basis",
    "amortization-verification-unknown",
    "program-match-unknown",
    "period-match-unknown",
    "currency-match-unknown",
    "unit-match-unknown",
    "actuals-completeness-unknown",
    "actuals-deduplication-unknown",
    "cancelled-order-reconciliation-unknown",
    "contract-current-unknown",
    "amendment-review-unknown",
    "prior-payment-exhausts-exposure",
    "mitigation-exceeds-exposure",
}


@pytest.mark.parametrize("recovery_case,expected", CASES, ids=lambda value: getattr(value, "case_id", None))
def test_capacity_commitment_oracle(recovery_case, expected):
    result = evaluate_recoverability(recovery_case)
    assert result.recoverability_state == expected["state"]
    assert result.economic_exposure == expected["economic_exposure"]
    assert result.net_exposure == expected["net_exposure"]
    assert result.recoverable_amount == expected["recoverable"]
    assert result.claimable_amount == expected["recoverable"]


def test_capacity_commitment_mandatory_and_red_team_matrix_present():
    actual = {recovery_case.case_id for recovery_case, _ in CASES}
    assert MANDATORY_CASE_IDS.issubset(actual)
    assert RED_TEAM_CASE_IDS.issubset(actual)


def test_capacity_commitment_unknown_integrity_fails_closed():
    recovery_case = case("unknown-integrity", program_matches=None)
    result = evaluate_recoverability(recovery_case)
    assert result.recoverability_state == RecoverabilityState.UNKNOWN
    assert result.economic_exposure > Decimal("0")
    assert result.recoverable_amount == Decimal("0")
    assert result.claimable_amount == Decimal("0")


def test_capacity_commitment_wrong_amortization_fails_closed():
    recovery_case = case("wrong-amortization-direct-test", amortization_verified=False)
    result = evaluate_recoverability(recovery_case)
    assert result.recoverability_state == RecoverabilityState.UNKNOWN
    assert result.economic_exposure == Decimal("100000")
    assert result.claimable_amount == Decimal("0")
    assert result.reasons == ("amortization_basis_not_verified",)


def test_capacity_commitment_rejects_negative_inputs():
    with pytest.raises(ValueError):
        evaluate_recoverability(
            RecoveryCase(
                case_id="negative",
                currency="EUR",
                committed_units=Decimal("100"),
                actual_units=Decimal("-1"),
                dedicated_cost=Decimal("1000"),
                amortization_basis_units=Decimal("100"),
            )
        )


def test_capacity_commitment_rejects_zero_unit_basis_for_amortized_cost():
    with pytest.raises(ValueError):
        evaluate_recoverability(
            RecoveryCase(
                case_id="zero-basis",
                currency="EUR",
                committed_units=Decimal("100"),
                actual_units=Decimal("50"),
                dedicated_cost=Decimal("1000"),
                amortization_basis_units=Decimal("0"),
            )
        )
