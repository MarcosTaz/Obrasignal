from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Sequence

Money = Decimal


class OptionType(str, Enum):
    RETAIN = "retain"
    RENEW = "renew"
    SWITCH = "switch"


@dataclass(frozen=True)
class SwitchingOption:
    option_id: str
    option_type: OptionType
    destination: str
    currency: str
    annual_run_cost: Money
    one_time_switching_cost: Money = Decimal("0")
    received_incentives: Money = Decimal("0")

    def validate(self) -> None:
        if not self.option_id.strip() or not self.destination.strip():
            raise ValueError("option id and destination are required")
        if len(self.currency) != 3 or self.currency.upper() != self.currency:
            raise ValueError("currency must be a three-letter uppercase code")
        if self.annual_run_cost < 0 or self.one_time_switching_cost < 0 or self.received_incentives < 0:
            raise ValueError("option costs and incentives cannot be negative")
        if self.option_type in {OptionType.RETAIN, OptionType.RENEW} and self.received_incentives != 0:
            raise ValueError("retain/renew options cannot carry migration incentives")


@dataclass(frozen=True)
class OptionResult:
    option: SwitchingOption
    horizon_years: int
    gross_total_cost: Money
    customer_cash_total_cost: Money
    gross_rank: int
    cash_rank: int


@dataclass(frozen=True)
class OptionComparison:
    currency: str
    horizon_years: int
    options: tuple[OptionResult, ...]
    economic_winner_id: str
    customer_cash_winner_id: str


def compare_options(options: Sequence[SwitchingOption], *, horizon_years: int = 3) -> OptionComparison:
    if horizon_years <= 0:
        raise ValueError("horizon_years must be positive")
    if len(options) < 2:
        raise ValueError("at least two options are required")

    seen = set()
    currencies = set()
    computed = []
    for option in options:
        option.validate()
        if option.option_id in seen:
            raise ValueError(f"duplicate option id: {option.option_id}")
        seen.add(option.option_id)
        currencies.add(option.currency)
        gross = option.annual_run_cost * horizon_years + option.one_time_switching_cost
        cash = gross - option.received_incentives
        computed.append((option, gross, cash))

    if len(currencies) != 1:
        raise ValueError("option comparison requires one normalized currency; provide explicit FX normalization first")

    gross_order = sorted(computed, key=lambda row: (row[1], row[0].option_id))
    cash_order = sorted(computed, key=lambda row: (row[2], row[0].option_id))
    gross_rank = {row[0].option_id: index + 1 for index, row in enumerate(gross_order)}
    cash_rank = {row[0].option_id: index + 1 for index, row in enumerate(cash_order)}

    results = tuple(
        OptionResult(
            option=option,
            horizon_years=horizon_years,
            gross_total_cost=gross,
            customer_cash_total_cost=cash,
            gross_rank=gross_rank[option.option_id],
            cash_rank=cash_rank[option.option_id],
        )
        for option, gross, cash in computed
    )
    return OptionComparison(
        currency=next(iter(currencies)),
        horizon_years=horizon_years,
        options=results,
        economic_winner_id=gross_order[0][0].option_id,
        customer_cash_winner_id=cash_order[0][0].option_id,
    )
