from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


ZERO = Decimal("0")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class FeeResult:
    verified_economic_result: Decimal
    fee_rate: Decimal
    fee_due: Decimal
    attribution_verified: bool


def calculate_success_fee(
    *,
    verified_cash_received: Decimal,
    verified_credit_received: Decimal = ZERO,
    fee_rate: Decimal,
    attribution_verified: bool,
) -> FeeResult:
    values = (verified_cash_received, verified_credit_received, fee_rate)
    if any(not value.is_finite() for value in values):
        raise ValueError("non-finite fee input")
    if verified_cash_received < ZERO or verified_credit_received < ZERO:
        raise ValueError("economic result cannot be negative")
    if fee_rate < ZERO or fee_rate > Decimal("1"):
        raise ValueError("fee_rate must be between 0 and 1")

    result = verified_cash_received + verified_credit_received
    fee = (
        (result * fee_rate).quantize(CENT, rounding=ROUND_HALF_UP)
        if attribution_verified
        else ZERO
    )
    return FeeResult(
        verified_economic_result=result,
        fee_rate=fee_rate,
        fee_due=fee,
        attribution_verified=attribution_verified,
    )
