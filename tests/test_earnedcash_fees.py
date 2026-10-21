from decimal import Decimal

import pytest

from earnedcash.fees import calculate_success_fee


def test_success_fee_is_zero_without_verified_attribution():
    result = calculate_success_fee(
        verified_cash_received=Decimal("10000"),
        verified_credit_received=Decimal("500"),
        fee_rate=Decimal("0.15"),
        attribution_verified=False,
    )
    assert result.verified_economic_result == Decimal("10500")
    assert result.fee_due == Decimal("0")


def test_success_fee_uses_only_verified_economic_result_when_attributed():
    result = calculate_success_fee(
        verified_cash_received=Decimal("10000"),
        verified_credit_received=Decimal("500"),
        fee_rate=Decimal("0.15"),
        attribution_verified=True,
    )
    assert result.verified_economic_result == Decimal("10500")
    assert result.fee_due == Decimal("1575.00")


def test_correct_zero_result_is_a_zero_fee_pass():
    result = calculate_success_fee(
        verified_cash_received=Decimal("0"),
        verified_credit_received=Decimal("0"),
        fee_rate=Decimal("0.15"),
        attribution_verified=True,
    )
    assert result.verified_economic_result == Decimal("0")
    assert result.fee_due == Decimal("0.00")


def test_fee_rounds_to_currency_cent_half_up():
    result = calculate_success_fee(
        verified_cash_received=Decimal("1.03"),
        fee_rate=Decimal("0.15"),
        attribution_verified=True,
    )
    assert result.fee_due == Decimal("0.15")


@pytest.mark.parametrize(
    "cash,credit,rate,error",
    [
        (Decimal("-1"), Decimal("0"), Decimal("0.15"), "economic result cannot be negative"),
        (Decimal("0"), Decimal("-1"), Decimal("0.15"), "economic result cannot be negative"),
        (Decimal("0"), Decimal("0"), Decimal("-0.01"), "fee_rate must be between 0 and 1"),
        (Decimal("0"), Decimal("0"), Decimal("1.01"), "fee_rate must be between 0 and 1"),
        (Decimal("NaN"), Decimal("0"), Decimal("0.15"), "non-finite fee input"),
    ],
)
def test_invalid_fee_inputs_fail_closed(cash, credit, rate, error):
    with pytest.raises(ValueError, match=error):
        calculate_success_fee(
            verified_cash_received=cash,
            verified_credit_received=credit,
            fee_rate=rate,
            attribution_verified=True,
        )
