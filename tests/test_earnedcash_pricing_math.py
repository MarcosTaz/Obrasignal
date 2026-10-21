from decimal import Decimal

from earnedcash.fees import calculate_success_fee


def test_verified_result_fee_math():
    result = calculate_success_fee(
        verified_cash_received=Decimal("10000"),
        fee_rate=Decimal("0.15"),
        attribution_verified=True,
    )
    assert result.fee_due == Decimal("1500.00")


def test_unattributed_result_has_no_fee_due():
    result = calculate_success_fee(
        verified_cash_received=Decimal("10000"),
        fee_rate=Decimal("0.15"),
        attribution_verified=False,
    )
    assert result.fee_due == Decimal("0")
