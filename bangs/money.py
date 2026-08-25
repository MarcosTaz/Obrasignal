from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
import re
from typing import Iterable

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")

class MoneyError(ValueError):
    pass

class CurrencyMismatch(MoneyError):
    pass


def as_decimal(value: Decimal | int | str | float) -> Decimal:
    if isinstance(value, bool):
        raise MoneyError("boolean is not a monetary value")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MoneyError("non-finite monetary value")
        value = repr(value)
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MoneyError("invalid monetary value") from exc
    if not result.is_finite():
        raise MoneyError("non-finite monetary value")
    return result


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        amount = as_decimal(self.amount)
        currency = str(self.currency or "").strip().upper()
        if amount < 0:
            raise MoneyError("money amount must be non-negative")
        if not _CURRENCY_RE.fullmatch(currency):
            raise MoneyError("currency must be an ISO-like three-letter code")
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "currency", currency)

    @classmethod
    def of(cls, amount: Decimal | int | str | float, currency: str) -> "Money":
        return cls(as_decimal(amount), currency)

    def plus(self, other: "Money") -> "Money":
        _require_same_currency(self, other)
        return Money(self.amount + other.amount, self.currency)

    def times(self, factor: Decimal | int | str | float) -> "Money":
        factor_d = as_decimal(factor)
        if factor_d < 0:
            raise MoneyError("money multiplier must be non-negative")
        return Money(self.amount * factor_d, self.currency)

    def difference(self, other: "Money") -> Decimal:
        _require_same_currency(self, other)
        return self.amount - other.amount

    def as_dict(self) -> dict[str, str]:
        return {"amount": format(self.amount, "f"), "currency": self.currency}


def _require_same_currency(left: Money, right: Money) -> None:
    if left.currency != right.currency:
        raise CurrencyMismatch(f"cannot combine {left.currency} and {right.currency} without explicit FX")


def sum_money(values: Iterable[Money], *, currency: str | None = None) -> Money | None:
    items = tuple(values)
    if not items:
        return Money.of(0, currency) if currency else None
    expected = currency.upper() if currency else items[0].currency
    total = Decimal("0")
    for item in items:
        if item.currency != expected:
            raise CurrencyMismatch(f"cannot combine {expected} and {item.currency} without explicit FX")
        total += item.amount
    return Money(total, expected)
