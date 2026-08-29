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
    "wrong-customer",
    "wrong-unit",
    "missing-call-off",
    "late-call-off-not-reconciled",
    "duplicate-volume",
    "cancelled-order-in-actuals",
    "wrong-amortization-basis",
    "amortization-verification-unknown",
    "asset-dedication-not-verified",
    "asset-dedication-verification-unknown",
    "mitigation-not-reviewed",
    "mitigation-review-unknown",
    "prior-recovery-not-reviewed",
    "prior-recovery-review-unknown",
    "notice-window-not-verified",
    "notice-window-verification-unknown",
    "wrong-contract",
    "contract-match-unknown",
    "wrong-amendment",
    "amendment-match-unknown",
    "customer-match-unknown",
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


@pytest.mark.parametrize(
    "field,reason",
    [
        ("amortization_verified", "amortization_basis_not_verified"),
        ("mitigation_reviewed", "mitigation_not_reviewed"),
        ("prior_recovery_reviewed", "prior_recovery_not_reviewed"),
        ("notice_window_verified", "notice_window_not_verified"),
        ("contract_matches", "wrong_contract"),
        ("amendment_matches", "wrong_amendment"),
        ("customer_matches", "wrong_customer"),
    ],
)
def test_capacity_commitment_material_integrity_failures_are_zero_claimable(field, reason):
    recovery_case = case(f"direct-{field}", **{field: False})
    result = evaluate_recoverability(recovery_case)
    assert result.recoverability_state == RecoverabilityState.UNKNOWN
    assert result.economic_exposure == Decimal("100000")
    assert result.claimable_amount == Decimal("0")
    assert result.reasons == (reason,)


def test_capacity_commitment_unverified_dedication_fails_closed_before_shared_asset_classification():
    recovery_case = case("unverified-dedication", asset_dedication_verified=False)
    result = evaluate_recoverability(recovery_case)
    assert result.recoverability_state == RecoverabilityState.UNKNOWN
    assert result.claimable_amount == Decimal("0")
    assert result.reasons == ("asset_dedication_not_verified",)


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


@pytest.mark.parametrize("currency", ["ＥＵＲ", "ΕΥΡ", "€UR", "EU1"])
def test_capacity_commitment_rejects_non_ascii_or_non_alpha_currency_codes(currency):
    with pytest.raises(ValueError, match="currency"):
        evaluate_recoverability(case("spoofed-currency", currency=currency))
