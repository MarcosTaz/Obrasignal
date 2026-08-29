from decimal import Decimal

import pytest

from factories.capacity_commitment.engine import RecoverabilityState, evaluate_recoverability
from factories.capacity_commitment.synthetic_cases import case


@pytest.mark.parametrize(
    "recovery_case,reason",
    [
        (
            case(
                "zero-unreviewed-mitigation",
                mitigation=Decimal("100000"),
                mitigation_reviewed=None,
            ),
            "mitigation_review_unknown",
        ),
        (
            case(
                "zero-unreviewed-prior-payment",
                prior_payment=Decimal("100000"),
                prior_recovery_reviewed=False,
            ),
            "prior_recovery_not_reviewed",
        ),
        (
            case(
                "zero-unverified-actuals",
                actual_units=Decimal("100000"),
                actuals_complete=None,
            ),
            "actuals_completeness_unknown",
        ),
        (
            case(
                "zero-wrong-program-mapping",
                actual_units=Decimal("100000"),
                program_matches=False,
            ),
            "wrong_program",
        ),
        (
            case(
                "zero-unverified-amortization",
                already_fully_amortized=True,
                amortization_verified=None,
            ),
            "amortization_verification_unknown",
        ),
        (
            case(
                "zero-already-paid-unreviewed",
                already_paid=True,
                prior_recovery_reviewed=None,
            ),
            "prior_recovery_review_unknown",
        ),
    ],
)
def test_zero_exposure_does_not_override_unknown_or_unverified_economic_inputs(recovery_case, reason):
    result = evaluate_recoverability(recovery_case)

    assert result.net_exposure == Decimal("0")
    assert result.recoverability_state is RecoverabilityState.UNKNOWN
    assert result.recoverable_amount == Decimal("0")
    assert result.claimable_amount == Decimal("0")
    assert result.reasons == (reason,)


def test_structural_zero_cost_does_not_require_irrelevant_entitlement_evidence():
    recovery_case = case(
        "zero-cost-structural",
        dedicated_cost=Decimal("0"),
        amortization_basis_units=Decimal("0"),
        explicit_recovery_right=None,
        contract_matches=None,
        notice_valid=None,
    )

    result = evaluate_recoverability(recovery_case)

    assert result.recoverability_state is RecoverabilityState.ZERO_EXPOSURE
    assert result.net_exposure == Decimal("0")
    assert result.reasons == ("no_net_exposure_remaining",)
