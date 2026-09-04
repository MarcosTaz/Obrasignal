from decimal import Decimal, Inexact, localcontext

from factories.capacity_commitment.engine import RecoverabilityState, evaluate_recoverability
from factories.capacity_commitment.synthetic_cases import case


def _case(case_id: str):
    return case(
        case_id,
        committed_units=Decimal("3"),
        actual_units=Decimal("1"),
        dedicated_cost=Decimal("100"),
        amortization_basis_units=Decimal("3"),
    )


def _evaluate_under_precision(precision: int):
    with localcontext() as ctx:
        ctx.prec = precision
        return evaluate_recoverability(_case("decimal-context-stability"))


def test_engine_result_is_independent_of_ambient_decimal_precision():
    low_precision = _evaluate_under_precision(6)
    high_precision = _evaluate_under_precision(40)

    assert low_precision == high_precision
    assert low_precision.recoverable_amount == high_precision.recoverable_amount
    assert low_precision.unit_amortization == high_precision.unit_amortization


def test_engine_is_independent_of_ambient_decimal_traps_and_exponent_limits():
    with localcontext() as ctx:
        ctx.prec = 6
        ctx.Emax = 9
        ctx.Emin = -9
        ctx.traps[Inexact] = True
        result = evaluate_recoverability(_case("decimal-context-traps"))

    assert result.recoverability_state is RecoverabilityState.RECOVERABLE
    assert result.claimable_amount > Decimal("0")


def test_engine_does_not_mutate_callers_decimal_context():
    with localcontext() as ctx:
        ctx.prec = 11
        ctx.Emax = 99
        evaluate_recoverability(_case("decimal-context-preserved"))
        assert ctx.prec == 11
        assert ctx.Emax == 99
