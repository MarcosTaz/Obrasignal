from decimal import Decimal

import pytest

from factories.capacity_commitment.engine import CommitmentState, RecoverabilityState, evaluate_recoverability
from factories.capacity_commitment.synthetic_cases import case


@pytest.mark.parametrize("commitment_state", [CommitmentState.FIRM, CommitmentState.FLEX_WINDOW])
def test_zero_effective_volume_commitment_cannot_become_recoverable(commitment_state):
    recovery_case = case(
        f"zero-{commitment_state.value.lower()}",
        commitment_state=commitment_state,
        committed_units=Decimal("0"),
        actual_units=Decimal("0"),
        dedicated_cost=Decimal("500000"),
        amortization_basis_units=Decimal("100000"),
    )

    result = evaluate_recoverability(recovery_case)

    assert result.economic_exposure == Decimal("500000")
    assert result.shortfall_units == Decimal("0")
    assert result.recoverability_state is RecoverabilityState.NON_RECOVERABLE
    assert result.recoverable_amount == Decimal("0")
    assert result.claimable_amount == Decimal("0")
    assert result.reasons == ("zero_effective_commitment",)


def test_positive_effective_flex_minimum_remains_eligible_for_normal_gates():
    recovery_case = case(
        "positive-flex-minimum",
        commitment_state=CommitmentState.FLEX_WINDOW,
        committed_units=Decimal("100000"),
        actual_units=Decimal("80000"),
    )

    result = evaluate_recoverability(recovery_case)

    assert result.recoverability_state is RecoverabilityState.RECOVERABLE
    assert result.claimable_amount == Decimal("100000")
