"""Truth-preserving composition of public execution-economics contracts.

Owners stay authoritative:
- Bid Economics: revenue/cost/margin/cash/guarantee economics.
- MOBILIZE: mobilization scenario calculation.
- BANGS: field observations and execution-cost assessment.
- Company State: company resources/constraints.

This module only composes owner outputs. It performs no FX, provider calls, or
cross-owner profit calculation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Iterable, Mapping

from bangs.costs import CostAssessment
from bangs.providers.base import ProviderResult, ProviderStatus
from bangs.true_cost import TrueJobCostAssessment
from bid_economics import BidEconomicsAssessment, Scenario
from company_state import CompanyState
from company_state_adapters import bangs_inputs, economics_constraints, mobilize_inputs
from mobilize import MobilizationAssessment, MobilizationContext, Mobilize, MobilizePolicy, RangeInput

CONTRACT_VERSION = "execution-economics.v1"


class CurrencyState(str, Enum):
    SINGLE = "SINGLE"
    UNKNOWN = "UNKNOWN"
    UNRESOLVED = "UNRESOLVED"


class ProviderAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class MoneyView:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        try:
            amount = self.amount if isinstance(self.amount, Decimal) else Decimal(str(self.amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("invalid monetary amount") from exc
        if not amount.is_finite():
            raise ValueError("monetary amount must be finite")
        currency = str(self.currency or "").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be explicit three-letter code")
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "currency", currency)

    @classmethod
    def owner(cls, money: Any | None) -> "MoneyView | None":
        return None if money is None else cls(money.amount, money.currency)

    @classmethod
    def amount_in(cls, amount: Decimal | None, currency: str | None) -> "MoneyView | None":
        return None if amount is None or currency is None else cls(amount, currency)

    def to_dict(self) -> dict[str, str]:
        return {"amount": format(self.amount, "f"), "currency": self.currency}


@dataclass(frozen=True)
class ProviderAvailabilityView:
    provider: str
    state: ProviderAvailability
    owner_status: str
    error_code: str | None
    essential: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "state": self.state.value,
            "owner_status": self.owner_status,
            "error_code": self.error_code,
            "essential": self.essential,
        }


@dataclass(frozen=True)
class ScopeReconciliation:
    """None means unknown; omission never means False/not-included."""

    mobilization_in_bid_execution_cost: bool | None = None
    bangs_execution_in_bid_execution_cost: bool | None = None


@dataclass(frozen=True)
class CompanyMobilizeSeed:
    context: MobilizationContext | None
    basis: dict[str, Any]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class ExecutionEconomicsAssessment:
    opportunity_id: str
    tenant_id: str
    currency_state: CurrencyState
    currencies: tuple[str, ...]
    known_bid_economics: dict[str, Any]
    known_mobilization_cost: MoneyView | None
    known_execution_cost: MoneyView | None
    execution_cost_complete: bool
    cash_exposure: dict[str, Any]
    mobilization_options: tuple[dict[str, Any], ...]
    company_state_basis: dict[str, Any]
    provider_availability: tuple[ProviderAvailabilityView, ...]
    scenario_basis: tuple[str, ...]
    source_basis: tuple[str, ...]
    unknown_components: tuple[str, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    contract_version: str = CONTRACT_VERSION

    @property
    def read_model(self) -> dict[str, Any]:
        known_costs: list[dict[str, Any]] = []
        estimated_costs: list[dict[str, Any]] = []
        if self.known_execution_cost:
            known_costs.append({
                "code": "bangs_execution_known_subtotal",
                "amount": self.known_execution_cost.to_dict(),
                "is_total": self.execution_cost_complete,
            })
        if self.known_mobilization_cost:
            estimated_costs.append({
                "code": "mobilize_selected_scenario",
                "amount": self.known_mobilization_cost.to_dict(),
                "note": "do not add across owner scopes until reconciliation is explicit",
            })
        if self.known_bid_economics.get("probable_execution_cost"):
            estimated_costs.append({
                "code": "bid_economics_probable_execution_cost",
                "amount": self.known_bid_economics["probable_execution_cost"],
                "note": "Bid Economics owner scope",
            })
        return {
            "KNOWN COSTS": known_costs,
            "ESTIMATED COSTS": estimated_costs,
            "ASSUMPTIONS": list(self.assumptions),
            "UNKNOWN COSTS": list(self.unknown_components),
            "CASH EXPOSURE": _json(self.cash_exposure),
            "MOBILIZATION OPTIONS": [_json(item) for item in self.mobilization_options],
            "SOURCE/EVIDENCE BASIS": list(self.source_basis),
            "WARNINGS": list(self.warnings),
            "BLOCKERS": list(self.blockers),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "opportunity_id": self.opportunity_id,
            "tenant_id": self.tenant_id,
            "currency_state": self.currency_state.value,
            "currencies": list(self.currencies),
            "known_bid_economics": _json(self.known_bid_economics),
            "known_mobilization_cost": self.known_mobilization_cost.to_dict() if self.known_mobilization_cost else None,
            "known_execution_cost": self.known_execution_cost.to_dict() if self.known_execution_cost else None,
            "execution_cost_complete": self.execution_cost_complete,
            "cash_exposure": _json(self.cash_exposure),
            "mobilization_options": [_json(item) for item in self.mobilization_options],
            "company_state_basis": _json(self.company_state_basis),
            "provider_availability": [item.to_dict() for item in self.provider_availability],
            "scenario_basis": list(self.scenario_basis),
            "source_basis": list(self.source_basis),
            "unknown_components": list(self.unknown_components),
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
            "read_model": self.read_model,
        }


def _json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, MoneyView):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(v) for v in value]
    return value


def _money_dict(money: Any | None) -> dict[str, str] | None:
    view = MoneyView.owner(money)
    return view.to_dict() if view else None


def _probable(bid: BidEconomicsAssessment):
    return next(item for item in bid.scenarios if item.scenario == Scenario.PROBABLE)


def _mobilization_option(item: Any, currency: str) -> dict[str, Any]:
    availability = getattr(item, "availability_state", "AVAILABLE" if item.available else "UNAVAILABLE")
    return {
        "scenario": item.scenario,
        "strategy": item.strategy,
        "vehicle_mode": item.vehicle_mode,
        "availability": availability,
        "comparable": item.comparable,
        "minimum_cost": MoneyView.amount_in(item.minimum_cost, currency),
        "probable_cost": MoneyView.amount_in(item.probable_cost, currency),
        "prudent_cost": MoneyView.amount_in(item.prudent_cost, currency),
        "missing_inputs": tuple(item.missing_inputs),
        "assumptions": tuple(item.assumptions),
        "warnings": tuple(item.warnings),
        "evidence": tuple(item.evidence),
    }


def _mobilization_globally_blocked(mobilization: MobilizationAssessment | None) -> bool:
    if mobilization is None:
        return True
    return any(
        getattr(item, "availability_state", "AVAILABLE" if item.available else "UNAVAILABLE") == "UNKNOWN"
        or (item.available and not item.comparable)
        for item in mobilization.alternative_scenarios
    )


def _provider_view(name: str, result: ProviderResult, essential: bool) -> ProviderAvailabilityView:
    if result.status is ProviderStatus.OK:
        state = ProviderAvailability.AVAILABLE
    elif result.status is ProviderStatus.UNAVAILABLE:
        state = ProviderAvailability.UNAVAILABLE
    else:
        state = ProviderAvailability.ERROR
    return ProviderAvailabilityView(name, state, result.status.value, result.error_code, essential)


def _cash_only(assessments: Iterable[CostAssessment]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {"code": line.code, "amount": MoneyView.owner(line.amount).to_dict(), "basis": line.basis.value}
        for assessment in assessments
        for line in assessment.lines
        if line.cash_only
    )


def company_state_execution_basis(state: CompanyState) -> dict[str, Any]:
    return {
        "mobilize": mobilize_inputs(state),
        "economics_constraints": economics_constraints(state),
        "bangs": bangs_inputs(state),
    }


def mobilization_context_from_company_state(state: CompanyState, template: MobilizationContext) -> CompanyMobilizeSeed:
    """Use only Q090's dedicated availability adapters, never totals/ownership."""
    basis = mobilize_inputs(state)
    workers = basis["workers"]
    vehicles = basis["own_vehicles_available"]
    if workers["state"] != "KNOWN":
        return CompanyMobilizeSeed(None, basis, ("COMPANY_AVAILABLE_CREW_UNKNOWN",))
    count = workers["value"]
    if isinstance(count, bool) or not isinstance(count, int):
        return CompanyMobilizeSeed(None, basis, ("COMPANY_AVAILABLE_CREW_INVALID",))
    if count <= 0:
        return CompanyMobilizeSeed(None, basis, ("COMPANY_AVAILABLE_CREW_ZERO",))
    blockers: list[str] = []
    own_vehicles: int | None = None
    if vehicles["state"] == "KNOWN":
        value = vehicles["value"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return CompanyMobilizeSeed(None, basis, ("COMPANY_AVAILABLE_VEHICLES_INVALID",))
        own_vehicles = value
    elif vehicles["state"] == "CONFLICT":
        blockers.append("COMPANY_AVAILABLE_VEHICLES_CONFLICT")
    else:
        blockers.append("COMPANY_AVAILABLE_VEHICLES_UNKNOWN")
    return CompanyMobilizeSeed(replace(template, workers=count, own_vehicles_available=own_vehicles), basis, tuple(blockers))


def compose_execution_economics(
    *,
    tenant_id: str,
    opportunity_id: str,
    bid: BidEconomicsAssessment,
    mobilization: MobilizationAssessment | None = None,
    bangs: TrueJobCostAssessment | None = None,
    company_state: CompanyState | None = None,
    provider_results: Mapping[str, ProviderResult] | None = None,
    essential_providers: Iterable[str] = (),
    cash_assessments: Iterable[CostAssessment] = (),
    reconciliation: ScopeReconciliation | None = None,
) -> ExecutionEconomicsAssessment:
    tenant = str(tenant_id or "").strip()
    opportunity = str(opportunity_id or "").strip()
    if not tenant or not opportunity:
        raise ValueError("tenant_id and opportunity_id are required")
    if bid.tenant_id != tenant:
        raise ValueError("TENANT_MISMATCH: bid economics")
    if bid.opportunity_id != opportunity:
        raise ValueError("OPPORTUNITY_MISMATCH: bid economics")
    if company_state is not None and company_state.account_id != tenant:
        raise ValueError("TENANT_MISMATCH: company state")

    reconciliation = reconciliation or ScopeReconciliation()
    probable = _probable(bid)
    unknowns = [f"bid:{item}" for item in bid.missing_inputs]
    warnings = [f"bid:{item}" for item in bid.warnings]
    assumptions = [f"bid:{item}" for item in bid.assumptions]
    blockers: list[str] = []
    source_basis = [f"bid:{bid.assessment_version}"]
    scenario_basis = [item.scenario.value for item in bid.scenarios]

    execution_known = MoneyView.owner(bangs.assessment.known_total) if bangs else None
    execution_complete = bool(bangs and bangs.total_job_cost_known)
    if bangs is None:
        unknowns.append("bangs:execution_cost")
    else:
        unknowns.extend(f"bangs:{item}" for item in bangs.assessment.unknown_components)
        warnings.extend(f"bangs:{item}" for item in bangs.assessment.warnings)
        source_basis.extend(f"bangs-cost-basis:{basis}" for basis in sorted({line.basis.value for line in bangs.assessment.lines}))
        if not execution_complete:
            blockers.append("EXECUTION_COST_PARTIAL")

    mobilization_blocked = _mobilization_globally_blocked(mobilization)
    selected_mobilization = (
        MoneyView.amount_in(mobilization.probable_cost, mobilization.currency)
        if mobilization and mobilization.probable_cost is not None and not mobilization_blocked
        else None
    )
    options: tuple[dict[str, Any], ...] = ()
    if mobilization is None:
        unknowns.append("mobilize:assessment")
        blockers.append("MOBILIZATION_NO_DEFENSIBLE_SCENARIO")
    else:
        options = tuple(_mobilization_option(item, mobilization.currency) for item in mobilization.alternative_scenarios)
        relevant_missing = set(mobilization.missing_inputs)
        for item in mobilization.alternative_scenarios:
            availability = getattr(item, "availability_state", "AVAILABLE" if item.available else "UNAVAILABLE")
            if availability == "UNKNOWN" or (item.available and not item.comparable):
                relevant_missing.update(item.missing_inputs)
        unknowns.extend(f"mobilize:{item}" for item in sorted(relevant_missing))
        warnings.extend(f"mobilize:{item}" for item in mobilization.warnings)
        assumptions.extend(f"mobilize:{item}" for item in mobilization.assumptions)
        source_basis.append(f"mobilize:{mobilization.contract_version}:{mobilization.policy_version}")
        scenario_basis.extend(item.scenario for item in mobilization.alternative_scenarios)
        if mobilization.recommended_scenario == "NO CLEAR WINNER" or mobilization.probable_cost is None or mobilization_blocked:
            blockers.append("MOBILIZATION_NO_DEFENSIBLE_SCENARIO")
        if mobilization_blocked and mobilization.recommended_scenario != "NO CLEAR WINNER":
            warnings.append("MOBILIZE_OWNER_RECOMMENDATION_WITH_UNRESOLVED_ALTERNATIVE_SUPPRESSED")

    if probable.execution_cost is None or bid.revenue.money is None:
        blockers.append("BID_ECONOMICS_INCOMPLETE")
    if selected_mobilization and probable.execution_cost and reconciliation.mobilization_in_bid_execution_cost is None:
        blockers.append("MOBILIZATION_BID_SCOPE_UNRECONCILED")
    if execution_known and probable.execution_cost and reconciliation.bangs_execution_in_bid_execution_cost is None:
        blockers.append("BANGS_BID_SCOPE_UNRECONCILED")
    if selected_mobilization and execution_known:
        warnings.append("NO_AUTOMATIC_BANGS_MOBILIZE_SUM: scopes may overlap")
    if probable.gross_profit and (selected_mobilization or execution_known):
        warnings.append("NO_COMBINED_PROFIT: Bid gross profit is not adjusted by composition")

    cash_only = _cash_only(cash_assessments)
    cash_exposure = {
        "working_capital_requirement": _money_dict(probable.working_capital_requirement),
        "guarantee_amount": _money_dict(bid.bonding_exposure),
        "guarantee_fees": _money_dict(bid.bonding_fees),
        "field_cash_only": list(cash_only),
        "note": "deposit is cash exposure, not economic cost; guarantee amount is not guarantee fee",
    }
    bid_view = {
        "revenue_basis": bid.revenue_basis.value,
        "revenue": _money_dict(bid.revenue.money),
        "probable_execution_cost": _money_dict(probable.execution_cost),
        "probable_gross_profit": _money_dict(probable.gross_profit),
        "probable_gross_margin_percent": format(probable.gross_margin_percent, "f") if probable.gross_margin_percent is not None else None,
        "working_capital_requirement": _money_dict(probable.working_capital_requirement),
        "bonding_exposure": _money_dict(bid.bonding_exposure),
        "bonding_fees": _money_dict(bid.bonding_fees),
        "confidence": bid.confidence,
        "scope_note": "owner-scope result only; composition does not manufacture combined profit",
    }

    company_basis: dict[str, Any] = {}
    if company_state:
        company_basis = company_state_execution_basis(company_state)
        source_basis.append(f"company-state:{company_state.contract_version}:{company_state.fingerprint}")
        for key in ("workers", "own_vehicles_available", "base_location"):
            if company_basis["mobilize"][key]["state"] != "KNOWN":
                unknowns.append(f"company_state:mobilize:{key}")
        for key, value in company_basis["economics_constraints"].items():
            if key not in {"account_id", "company_state_fingerprint"} and value["state"] != "KNOWN":
                unknowns.append(f"company_state:economics:{key}")

    essential = frozenset(str(item) for item in essential_providers)
    provider_views: list[ProviderAvailabilityView] = []
    for name, result in sorted((provider_results or {}).items()):
        view = _provider_view(name, result, name in essential)
        provider_views.append(view)
        source_basis.append(f"provider:{name}:{view.owner_status}")
        if view.state is not ProviderAvailability.AVAILABLE:
            unknowns.append(f"provider:{name}")
            if view.essential:
                blockers.append(f"ESSENTIAL_PROVIDER_{view.state.value}:{name}")

    currencies = {bid.currency}
    for money in (selected_mobilization, execution_known):
        if money:
            currencies.add(money.currency)
    for money in (probable.working_capital_requirement, bid.bonding_exposure, bid.bonding_fees):
        if money:
            currencies.add(money.currency)
    for item in cash_only:
        currencies.add(item["amount"]["currency"])
    if not currencies:
        currency_state = CurrencyState.UNKNOWN
    elif len(currencies) == 1:
        currency_state = CurrencyState.SINGLE
    else:
        currency_state = CurrencyState.UNRESOLVED
        blockers.append("MULTI_CURRENCY_UNRESOLVED")
        warnings.append("NO_FX_APPLIED")

    return ExecutionEconomicsAssessment(
        opportunity, tenant, currency_state, tuple(sorted(currencies)), bid_view,
        selected_mobilization, execution_known, execution_complete, cash_exposure,
        options, company_basis, tuple(provider_views), tuple(dict.fromkeys(scenario_basis)),
        tuple(dict.fromkeys(source_basis)), tuple(dict.fromkeys(unknowns)),
        tuple(dict.fromkeys(assumptions)), tuple(dict.fromkeys(warnings)), tuple(dict.fromkeys(blockers)),
    )


def recompute_mobilization_what_if(
    context: MobilizationContext,
    policy: MobilizePolicy,
    *,
    hotel_rate: Decimal | int | str | None = None,
    distance_km_one_way: Decimal | int | str | None = None,
    crew_size: int | None = None,
    working_days: int | None = None,
    hotel_available: bool | str | None = None,
) -> MobilizationAssessment:
    """Bounded deterministic what-if delegated to MOBILIZE; no forecasting."""
    revised_context, revised_policy = context, policy
    if distance_km_one_way is not None:
        revised_context = replace(revised_context, distance_km_one_way=RangeInput.scalar(
            distance_km_one_way, quality="ESTIMATED", source="what-if override: distance_km_one_way"))
    if crew_size is not None:
        revised_context = replace(revised_context, workers=crew_size)
    if working_days is not None:
        revised_context = replace(revised_context, working_days=working_days)
    if hotel_available is not None:
        revised_context = replace(revised_context, hotel_available=hotel_available)
    if hotel_rate is not None:
        revised_policy = replace(revised_policy, accommodation_per_worker_night=RangeInput.scalar(
            hotel_rate, quality="ESTIMATED", source="what-if override: hotel_rate"))
    return Mobilize.evaluate(revised_context, revised_policy)
