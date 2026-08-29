from decimal import Decimal, localcontext

from factories.capacity_commitment.engine import evaluate_recoverability
from factories.capacity_commitment.synthetic_cases import case


def _evaluate_under_precision(precision: int):
    recovery_case = case(
        "decimal-context-stability",
        committed_units=Decimal("3"),
        actual_units=Decimal("1"),
        dedicated_cost=Decimal("100"),
        amortization_basis_units=Decimal("3"),
    )
    with localcontext() as ctx:
        ctx.prec = precision
        return evaluate_recoverability(recovery_case)


def test_engine_result_is_independent_of_ambient_decimal_precision():
    low_precision = _evaluate_under_precision(6)
    high_precision = _evaluate_under_precision(40)

    assert low_precision == high_precision
    assert low_precision.recoverable_amount == high_precision.recoverable_amount
    assert low_precision.unit_amortization == high_precision.unit_amortization


def test_engine_does_not_mutate_callers_decimal_context():
    recovery_case = case(
        "decimal-context-preserved",
        committed_units=Decimal("3"),
        actual_units=Decimal("1"),
        dedicated_cost=Decimal("100"),
        amortization_basis_units=Decimal("3"),
    )
    with localcontext() as ctx:
        ctx.prec = 11
        evaluate_recoverability(recovery_case)
        assert ctx.prec == 11
