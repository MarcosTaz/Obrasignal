"""Deterministic one-opportunity bid economics for ObraSignal.

This module is deliberately not an estimating suite, accounting system, portfolio
optimizer or GO/NO-GO engine. It makes profit, cash exposure, guarantee exposure
and uncertainty explicit from caller-supplied facts/estimates/assumptions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, getcontext
from enum import Enum
import hashlib
import json
from typing import Iterable

getcontext().prec = 38
ASSESSMENT_VERSION = "bid-economics.v0"


class InputBasis(str, Enum):
    FACT = "FACT"
    ESTIMATE = "ESTIMATE"
    ASSUMPTION = "ASSUMPTION"
    UNKNOWN = "UNKNOWN"


class RevenueBasis(str, Enum):
    PUBLISHED_ESTIMATED_VALUE = "PUBLISHED_ESTIMATED_VALUE"
    BID_PRICE = "BID_PRICE"
    TARGET_PRICE = "TARGET_PRICE"
    AWARD_VALUE = "AWARD_VALUE"
    UNKNOWN = "UNKNOWN"


class CostCategory(str, Enum):
    LABOUR = "LABOUR"
    MATERIAL = "MATERIAL"
    EQUIPMENT = "EQUIPMENT"
    SUBCONTRACT = "SUBCONTRACT"
    MOBILIZATION = "MOBILIZATION"
    PRELIMINARIES = "PRELIMINARIES"
    INSURANCE = "INSURANCE"
    BONDING = "BONDING"
    FINANCING = "FINANCING"
    OVERHEAD = "OVERHEAD"
    CONTINGENCY = "CONTINGENCY"
    OTHER = "OTHER"


class CostNature(str, Enum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    BID_PREPARATION = "BID_PREPARATION"


class Scenario(str, Enum):
    MINIMUM = "MINIMUM"
    PROBABLE = "PROBABLE"
    PRUDENT = "PRUDENT"


class PaymentTerm(str, Enum):
    CASH = "CASH"
    NET30 = "NET30"
    NET60 = "NET60"
    NET90 = "NET90"
    CUSTOM = "CUSTOM"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        try:
            amount = self.amount if isinstance(self.amount, Decimal) else Decimal(str(self.amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("invalid monetary amount") from exc
        if not amount.is_finite():
            raise ValueError("monetary amount must be finite")
        currency = str(self.currency or "").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a 3-letter code")
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "currency", currency)

    def _same(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError("MULTI_CURRENCY_UNRESOLVED")

    def __add__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._same(other)
        return Money(self.amount - other.amount, self.currency)

    def scale(self, factor: Decimal | int | str) -> "Money":
        return Money(self.amount * Decimal(str(factor)), self.currency)


@dataclass(frozen=True)
class ScenarioMoney:
    minimum: Money
    probable: Money
    prudent: Money

    def __post_init__(self):
        currencies = {self.minimum.currency, self.probable.currency, self.prudent.currency}
        if len(currencies) != 1:
            raise ValueError("MULTI_CURRENCY_UNRESOLVED")
        for money in (self.minimum, self.probable, self.prudent):
            if money.amount < 0:
                raise ValueError("cost amounts cannot be negative")
        if self.prudent.amount < self.probable.amount:
            raise ValueError("prudent cost cannot be below probable cost")

    def for_scenario(self, scenario: Scenario) -> Money:
        return {
            Scenario.MINIMUM: self.minimum,
            Scenario.PROBABLE: self.probable,
            Scenario.PRUDENT: self.prudent,
        }[scenario]


@dataclass(frozen=True)
class EconomicValue:
    money: Money | None
    basis: InputBasis = InputBasis.UNKNOWN
    source: str = ""

    def __post_init__(self):
        if self.money is None and self.basis != InputBasis.UNKNOWN:
            raise ValueError("missing money must use UNKNOWN basis")
        if self.money is not None and self.money.amount < 0:
            raise ValueError("economic values cannot be negative")


@dataclass(frozen=True)
class CostComponent:
    category: CostCategory
    nature: CostNature
    amounts: ScenarioMoney | None
    basis: InputBasis
    source: str = ""
    note: str = ""

    def __post_init__(self):
        if self.amounts is None and self.basis != InputBasis.UNKNOWN:
            raise ValueError("unknown cost must use UNKNOWN basis")
        if self.amounts is not None and self.basis == InputBasis.UNKNOWN:
            raise ValueError("known cost cannot use UNKNOWN basis")


@dataclass(frozen=True)
class GuaranteeExposure:
    kind: str
    amount: EconomicValue
    fee: EconomicValue = field(default_factory=lambda: EconomicValue(None))


@dataclass(frozen=True)
class PaymentTerms:
    contractual_term: PaymentTerm = PaymentTerm.UNKNOWN
    custom_days: int | None = None
    expected_payment_days: int | None = None
    retention_percent: Decimal | None = None
    advance_percent: Decimal | None = None

    def __post_init__(self):
        if self.contractual_term == PaymentTerm.CUSTOM and self.custom_days is None:
            raise ValueError("CUSTOM payment term requires custom_days")
        for name, value in (("custom_days", self.custom_days), ("expected_payment_days", self.expected_payment_days)):
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")
        for name, value in (("retention_percent", self.retention_percent), ("advance_percent", self.advance_percent)):
            if value is not None:
                value = Decimal(str(value))
                if value < 0 or value > 100:
                    raise ValueError(f"{name} must be between 0 and 100")
                object.__setattr__(self, name, value)

    @property
    def contractual_days(self) -> int | None:
        return {
            PaymentTerm.CASH: 0,
            PaymentTerm.NET30: 30,
            PaymentTerm.NET60: 60,
            PaymentTerm.NET90: 90,
            PaymentTerm.CUSTOM: self.custom_days,
            PaymentTerm.UNKNOWN: None,
        }[self.contractual_term]

    @property
    def observed_or_contractual_days(self) -> int | None:
        return self.expected_payment_days if self.expected_payment_days is not None else self.contractual_days


@dataclass(frozen=True)
class BidEconomicsPolicy:
    version: str = "bid-economics-policy.v0"
    high_working_capital_absolute: Money | None = None


@dataclass(frozen=True)
class BidEconomicsInput:
    opportunity_id: str
    tenant_id: str
    currency: str
    revenue: EconomicValue = field(default_factory=lambda: EconomicValue(None))
    revenue_basis: RevenueBasis = RevenueBasis.UNKNOWN
    cost_components: tuple[CostComponent, ...] = ()
    guarantees: tuple[GuaranteeExposure, ...] = ()
    insurance_exposure: EconomicValue = field(default_factory=lambda: EconomicValue(None))
    payment_terms: PaymentTerms = field(default_factory=PaymentTerms)
    duration_months: Decimal | None = None
    target_margin_percent: Decimal | None = None
    assumptions: tuple[str, ...] = ()

    def __post_init__(self):
        currency = str(self.currency or "").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a 3-letter code")
        object.__setattr__(self, "currency", currency)
        if not self.opportunity_id or not self.tenant_id:
            raise ValueError("opportunity_id and tenant_id are required")
        if self.revenue.money is not None and self.revenue.money.currency != currency:
            raise ValueError("MULTI_CURRENCY_UNRESOLVED")
        if self.revenue.money is None and self.revenue_basis != RevenueBasis.UNKNOWN:
            raise ValueError("known revenue basis requires revenue amount")
        if self.revenue.money is not None and self.revenue_basis == RevenueBasis.UNKNOWN:
            raise ValueError("known revenue requires explicit revenue basis")
        if self.duration_months is not None:
            duration = Decimal(str(self.duration_months))
            if duration <= 0:
                raise ValueError("duration_months must be positive")
            object.__setattr__(self, "duration_months", duration)
        if self.target_margin_percent is not None:
            margin = Decimal(str(self.target_margin_percent))
            if margin < 0 or margin >= 100:
                raise ValueError("target_margin_percent must be in [0, 100)")
            object.__setattr__(self, "target_margin_percent", margin)


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    direct_cost: Money | None
    indirect_cost: Money | None
    execution_cost: Money | None
    bid_preparation_cost: Money | None
    gross_profit: Money | None
    gross_margin_percent: Decimal | None
    markup_percent: Decimal | None
    working_capital_requirement: Money | None
    economic_break_even_price: Money | None
    target_margin_price: Money | None


@dataclass(frozen=True)
class BidEconomicsAssessment:
    opportunity_id: str
    tenant_id: str
    currency: str
    revenue_basis: RevenueBasis
    revenue: EconomicValue
    scenarios: tuple[ScenarioResult, ...]
    bonding_exposure: Money | None
    bonding_fees: Money | None
    insurance_exposure: EconomicValue
    payment_terms: PaymentTerms
    missing_inputs: tuple[str, ...]
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]
    confidence: str
    assessment_version: str
    policy_version: str
    input_fingerprint: str
    generated_at: datetime


def _money_sum(values: Iterable[Money], currency: str) -> Money:
    total = Money(Decimal("0"), currency)
    for value in values:
        total = total + value
    return total


def margin_percent(profit: Money, revenue: Money) -> Decimal | None:
    profit._same(revenue)
    if revenue.amount <= 0:
        return None
    return (profit.amount / revenue.amount) * Decimal("100")


def markup_percent(profit: Money, cost: Money) -> Decimal | None:
    profit._same(cost)
    if cost.amount <= 0:
        return None
    return (profit.amount / cost.amount) * Decimal("100")


def target_margin_price(cost: Money, target_margin_percent_value: Decimal) -> Money:
    pct = Decimal(str(target_margin_percent_value))
    if pct < 0 or pct >= 100:
        raise ValueError("target margin must be in [0, 100)")
    return Money(cost.amount / (Decimal("1") - pct / Decimal("100")), cost.currency)


def _component_totals(data: BidEconomicsInput, scenario: Scenario):
    known = [c for c in data.cost_components if c.amounts is not None]
    currencies = {c.amounts.for_scenario(scenario).currency for c in known}
    if currencies and currencies != {data.currency}:
        raise ValueError("MULTI_CURRENCY_UNRESOLVED")
    by_nature = {}
    for nature in CostNature:
        vals = [c.amounts.for_scenario(scenario) for c in known if c.nature == nature]
        by_nature[nature] = _money_sum(vals, data.currency)
    return by_nature


def _working_capital(data: BidEconomicsInput, execution_cost: Money | None, revenue: Money | None) -> Money | None:
    days = data.payment_terms.observed_or_contractual_days
    if execution_cost is None or data.duration_months is None or days is None:
        return None
    monthly_burn = execution_cost.amount / data.duration_months
    lag_funding = min(execution_cost.amount, monthly_burn * Decimal(days) / Decimal("30"))
    advance = Decimal("0")
    retention = Decimal("0")
    if revenue is not None and data.payment_terms.advance_percent is not None:
        advance = revenue.amount * data.payment_terms.advance_percent / Decimal("100")
    if revenue is not None and data.payment_terms.retention_percent is not None:
        retention = revenue.amount * data.payment_terms.retention_percent / Decimal("100")
    requirement = max(Decimal("0"), lag_funding + retention - advance)
    return Money(requirement, data.currency)


def _fingerprint(data: BidEconomicsInput, policy: BidEconomicsPolicy) -> str:
    def normalize(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, tuple):
            return [normalize(v) for v in value]
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in sorted(value.items())}
        return value
    payload = {"input": normalize(asdict(data)), "policy": normalize(asdict(policy))}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def evaluate_bid_economics(
    data: BidEconomicsInput,
    policy: BidEconomicsPolicy | None = None,
    *,
    generated_at: datetime | None = None,
) -> BidEconomicsAssessment:
    """Evaluate one opportunity without making a pursuit decision."""
    policy = policy or BidEconomicsPolicy()
    missing = []
    warnings = []
    if data.revenue.money is None:
        missing.append("REVENUE")
    unknown_components = [c.category.value for c in data.cost_components if c.amounts is None]
    if unknown_components:
        missing.extend(f"COST:{name}" for name in sorted(set(unknown_components)))
        warnings.append("MISSING_MAJOR_COST")
    if not data.cost_components:
        missing.append("COST_COMPONENTS")
        warnings.append("MISSING_MAJOR_COST")
    if data.payment_terms.contractual_term == PaymentTerm.UNKNOWN:
        missing.append("PAYMENT_TERM")
        warnings.append("PAYMENT_TERM_UNKNOWN")
    if not data.guarantees:
        missing.append("BONDING")
        warnings.append("BONDING_UNKNOWN")

    scenario_results = []
    for scenario in Scenario:
        totals = _component_totals(data, scenario)
        direct = totals[CostNature.DIRECT]
        indirect = totals[CostNature.INDIRECT]
        bid_prep = totals[CostNature.BID_PREPARATION]
        execution_known = direct + indirect
        execution_complete = bool(data.cost_components) and not any(
            c.amounts is None and c.nature != CostNature.BID_PREPARATION for c in data.cost_components
        )
        execution = execution_known if execution_complete else None
        revenue = data.revenue.money
        profit = revenue - execution if revenue is not None and execution is not None else None
        margin = margin_percent(profit, revenue) if profit is not None else None
        markup = markup_percent(profit, execution) if profit is not None else None
        wc = _working_capital(data, execution, revenue)
        break_even = execution
        target_price = (
            target_margin_price(execution, data.target_margin_percent)
            if execution is not None and data.target_margin_percent is not None else None
        )
        scenario_results.append(ScenarioResult(
            scenario=scenario,
            direct_cost=direct if execution_complete else None,
            indirect_cost=indirect if execution_complete else None,
            execution_cost=execution,
            bid_preparation_cost=bid_prep,
            gross_profit=profit,
            gross_margin_percent=margin,
            markup_percent=markup,
            working_capital_requirement=wc,
            economic_break_even_price=break_even,
            target_margin_price=target_price,
        ))
        if scenario == Scenario.PROBABLE and margin is not None and margin < 0:
            warnings.append("NEGATIVE_PROBABLE_MARGIN")
        if scenario == Scenario.PRUDENT and margin is not None and margin < 0:
            warnings.append("NEGATIVE_PRUDENT_MARGIN")

    guarantee_amounts = [g.amount.money for g in data.guarantees if g.amount.money is not None]
    guarantee_fees = [g.fee.money for g in data.guarantees if g.fee.money is not None]
    for money in [m for m in guarantee_amounts + guarantee_fees if m is not None]:
        if money.currency != data.currency:
            raise ValueError("MULTI_CURRENCY_UNRESOLVED")
    bonding_exposure = _money_sum(guarantee_amounts, data.currency) if guarantee_amounts else None
    bonding_fees = _money_sum(guarantee_fees, data.currency) if guarantee_fees else None

    probable_wc = next(r.working_capital_requirement for r in scenario_results if r.scenario == Scenario.PROBABLE)
    threshold = policy.high_working_capital_absolute
    if threshold is not None:
        if threshold.currency != data.currency:
            raise ValueError("MULTI_CURRENCY_UNRESOLVED")
        if probable_wc is not None and probable_wc.amount > threshold.amount:
            warnings.append("HIGH_WORKING_CAPITAL")

    known_major = sum(1 for x in (data.revenue.money, scenario_results[1].execution_cost, probable_wc) if x is not None)
    confidence = "HIGH" if not missing and known_major == 3 else "MEDIUM" if known_major >= 2 else "LOW" if known_major else "UNKNOWN"
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return BidEconomicsAssessment(
        opportunity_id=data.opportunity_id,
        tenant_id=data.tenant_id,
        currency=data.currency,
        revenue_basis=data.revenue_basis,
        revenue=data.revenue,
        scenarios=tuple(scenario_results),
        bonding_exposure=bonding_exposure,
        bonding_fees=bonding_fees,
        insurance_exposure=data.insurance_exposure,
        payment_terms=data.payment_terms,
        missing_inputs=tuple(dict.fromkeys(missing)),
        warnings=tuple(dict.fromkeys(warnings)),
        assumptions=tuple(data.assumptions),
        confidence=confidence,
        assessment_version=ASSESSMENT_VERSION,
        policy_version=policy.version,
        input_fingerprint=_fingerprint(data, policy),
        generated_at=timestamp,
    )


def recalculate_bid_economics(
    data: BidEconomicsInput,
    *,
    payment_days: int | None = None,
    material_multiplier: Decimal | str | int | None = None,
    labour_multiplier: Decimal | str | int | None = None,
    generated_at: datetime | None = None,
) -> BidEconomicsAssessment:
    """Limited structured what-if API; arbitrary formulas are intentionally unsupported."""
    multipliers = {
        CostCategory.MATERIAL: Decimal(str(material_multiplier)) if material_multiplier is not None else None,
        CostCategory.LABOUR: Decimal(str(labour_multiplier)) if labour_multiplier is not None else None,
    }
    if any(value is not None and value < 0 for value in multipliers.values()):
        raise ValueError("what-if multipliers cannot be negative")
    components = []
    for component in data.cost_components:
        factor = multipliers.get(component.category)
        if factor is None or component.amounts is None:
            components.append(component)
            continue
        a = component.amounts
        components.append(CostComponent(
            category=component.category,
            nature=component.nature,
            amounts=ScenarioMoney(a.minimum.scale(factor), a.probable.scale(factor), a.prudent.scale(factor)),
            basis=InputBasis.ASSUMPTION,
            source="what-if override",
            note=component.note,
        ))
    terms = data.payment_terms
    if payment_days is not None:
        terms = PaymentTerms(
            contractual_term=terms.contractual_term,
            custom_days=terms.custom_days,
            expected_payment_days=payment_days,
            retention_percent=terms.retention_percent,
            advance_percent=terms.advance_percent,
        )
    revised = BidEconomicsInput(
        opportunity_id=data.opportunity_id,
        tenant_id=data.tenant_id,
        currency=data.currency,
        revenue=data.revenue,
        revenue_basis=data.revenue_basis,
        cost_components=tuple(components),
        guarantees=data.guarantees,
        insurance_exposure=data.insurance_exposure,
        payment_terms=terms,
        duration_months=data.duration_months,
        target_margin_percent=data.target_margin_percent,
        assumptions=data.assumptions + ("WHAT_IF_OVERRIDE",),
    )
    return evaluate_bid_economics(revised, generated_at=generated_at)
