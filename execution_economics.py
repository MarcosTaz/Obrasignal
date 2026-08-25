"""Public composition contract for execution economics.

This module composes public outputs owned by Bid Economics, MOBILIZE, BANGS and
Company State. It deliberately does not recalculate owner economics, perform FX,
call providers, or manufacture a combined/"true" profit from partial inputs.
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
    """Composition DTO only; owners remain authoritative for money arithmetic."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        try:
            value = self.amount if isinstance(self.amount, Decimal) else Decimal(str(self.amount))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("invalid monetary amount") from exc
        if not value.is_finite():
            raise ValueError("monetary amount must be finite")
        currency = str(self.currency or "").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be explicit three-letter code")
        object.__setattr__(self, "amount", value)
        object.__setattr__(self, "currency", currency)

    @classmethod
    def from_owner_money(cls, money: Any | None) -> "MoneyView | None":
        if money is None:
            return None
        return cls(money.amount, money.currency)

    @classmethod
    def from_amount(cls, amount: Decimal | None, currency: str | None) -> "MoneyView | None":
        if amount is None or currency is None:
            return None
        return cls(amount, currency)

    def to_dict(self) -> dict[str, str]:
        return {"amount": format(self.amount, "f"), "currency": self.currency}


@dataclass(frozen=True)
class ProviderAvailabilityView:
    provider: str
    state: ProviderAvailability
    owner_status: str
    error_code: str | None = None
    essential: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "state": self.state.value,
            "owner_status": self.owner_status,
            "error_code": self.error_code,
            "essential": self.essential,
        }


@dataclass(frozen=True)
class MobilizationOptionView:
    scenario: str
    strategy: str
    vehicle_mode: str
    availability: str
    comparable: bool
    probable_cost: MoneyView | None
    minimum_cost: MoneyView | None
    prudent_cost: MoneyView | None
    missing_inputs: tuple[str, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "strategy": self.strategy,
            "vehicle_mode": self.vehicle_mode,
            "availability": self.availability,
            "comparable": self.comparable,
            "probable_cost": self.probable_cost.to_dict() if self.probable_cost else None,
            "minimum_cost": self.minimum_cost.to_dict() if self.minimum_cost else None,
            "prudent_cost": self.prudent_cost.to_dict() if self.prudent_cost else None,
            "missing_inputs": list(self.missing_inputs),
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
            "evidence": [_json_safe(item) for item in self.evidence],
        }


@dataclass(frozen=True)
class ExecutionEconomicsAssessment:
    opportunity_id: str
    tenant_id: str
    contract_version: str
    currency_state: CurrencyState
    currencies: tuple[str, ...]
    known_bid_economics: dict[str, Any]
    known_mobilization_cost: MoneyView | None
    known_execution_cost: MoneyView | None
    execution_cost_complete: bool
    cash_exposure: dict[str, Any]
    mobilization_options: tuple[MobilizationOptionView, ...]
    company_state_basis: dict[str, Any]
    provider_availability: tuple[ProviderAvailabilityView, ...]
    scenario_basis: tuple[str, ...]
    source_basis: tuple[str, ...]
    unknown_components: tuple[str, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def read_model(self) -> dict[str, Any]:
        known_costs: list[dict[str, Any]] = []
        estimated_costs: list[dict[str, Any]] = []
        if self.known_execution_cost is not None:
            known_costs.append({
                "code": "bangs_execution_known_subtotal",
                "amount": self.known_execution_cost.to_dict(),
                "is_total": self.execution_cost_complete,
            })
        if self.known_mobilization_cost is not None:
            estimated_costs.append({
                "code": "mobilize_selected_scenario",
                "amount": self.known_mobilization_cost.to_dict(),
                "note": "scenario output; do not add to BANGS/Bid costs until scope reconciliation is explicit",
            })
        bid_execution = self.known_bid_economics.get("probable_execution_cost")
        if bid_execution is not None:
            estimated_costs.append({
                "code": "bid_economics_probable_execution_cost",
                "amount": bid_execution,
                "note": "Bid Economics owner scope",
            })
        return {
            "KNOWN COSTS": known_costs,
            "ESTIMATED COSTS": estimated_costs,
            "ASSUMPTIONS": list(self.assumptions),
            "UNKNOWN COSTS": list(self.unknown_components),
            "CASH EXPOSURE": self.cash_exposure,
            "MOBILIZATION OPTIONS": [item.to_dict() for item in self.mobilization_options],
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
            "known_bid_economics": _json_safe(self.known_bid_economics),
            "known_mobilization_cost": self.known_mobilization_cost.to_dict() if self.known_mobilization_cost else None,
            "known_execution_cost": self.known_execution_cost.to_dict() if self.known_execution_cost else None,
            "execution_cost_complete": self.execution_cost_complete,
            "cash_exposure": _json_safe(self.cash_exposure),
            "mobilization_options": [item.to_dict() for item in self.mobilization_options],
            "company_state_basis": _json_safe(self.company_state_basis),
            "provider_availability": [item.to_dict() for item in self.provider_availability],
            "scenario_basis": list(self.scenario_basis),
            "source_basis": list(self.source_basis),
            "unknown_components": list(self.unknown_components),
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
            "read_model": self.read_model,
        }


@dataclass(frozen=True)
class CompanyMobilizeSeed:
    context: MobilizationContext | None
    basis: dict[str, Any]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class ScopeReconciliation:
    """Whether external owner costs are already represented inside Bid Economics.

    None is deliberate: an omitted answer is unknown, not False.
    """

    mobilization_in_bid_execution_cost: bool | None = None
    bangs_execution_in_bid_execution_cost: bool | None = None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, MoneyView):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value


def _money_dict(money: Any | None) -> dict[str, str] | None:
    view = MoneyView.from_owner_money(money)
    return view.to_dict() if view else None


def _probable_bid_result(bid: BidEconomicsAssessment):
    return next(item for item in bid.scenarios if item.scenario == Scenario.PROBABLE)


def _provider_view(name: str, result: ProviderResult, *, essential: bool) -> ProviderAvailabilityView:
    if result.status is ProviderStatus.OK:
        state = ProviderAvailability.AVAILABLE
    elif result.status is ProviderStatus.UNAVAILABLE:
        state = ProviderAvailability.UNAVAILABLE
    else:
        state = ProviderAvailability.ERROR
    return ProviderAvailabilityView(
        provider=name,
        state=state,
        owner_status=result.status.value,
        error_code=result.error_code,
        essential=essential,
    )


def _mobilization_options(mobilization: MobilizationAssessment | None) -> tuple[MobilizationOptionView, ...]:
    if mobilization is None:
        return ()
    result = []
    for item in mobilization.alternative_scenarios:
        result.append(MobilizationOptionView(
            scenario=item.scenario,
            strategy=item.strategy,
            vehicle_mode=item.vehicle_mode,
            availability=getattr(item, "availability_state", "AVAILABLE" if item.available else "UNAVAILABLE"),
            comparable=item.comparable,
            probable_cost=MoneyView.from_amount(item.probable_cost, mobilization.currency),
            minimum_cost=MoneyView.from_amount(item.minimum_cost, mobilization.currency),
            prudent_cost=MoneyView.from_amount(item.prudent_cost, mobilization.currency),
            missing_inputs=tuple(item.missing_inputs),
            assumptions=tuple(item.assumptions),
            warnings=tuple(item.warnings),
            evidence=tuple(item.evidence),
        ))
    return tuple(result)


def _bangs_execution(bangs: TrueJobCostAssessment | None) -> tuple[MoneyView | None, bool, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if bangs is None:
        return None, False, ("bangs:execution_cost",), (), ()
    assessment = bangs.assessment
    known = MoneyView.from_owner_money(assessment.known_total)
    unknowns = tuple(f"bangs:{item}" for item in assessment.unknown_components)
    warnings = tuple(f"bangs:{item}" for item in assessment.warnings)
    bases = tuple(sorted({line.basis.value for line in assessment.lines}))
    return known, bangs.total_job_cost_known, unknowns, warnings, bases


def _cash_only_lines(assessments: Iterable[CostAssessment]) -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    for assessment in assessments:
        for line in assessment.lines:
            if line.cash_only:
                result.append({
                    "code": line.code,
                    "amount": MoneyView.from_owner_money(line.amount).to_dict(),
                    "basis": line.basis.value,
                })
    return tuple(result)


def company_state_execution_basis(state: CompanyState) -> dict[str, Any]:
    """Read Company State only through its public neutral consumer adapters."""
    return {
        "mobilize": mobilize_inputs(state),
        "economics_constraints": economics_constraints(state),
        "bangs": bangs_inputs(state),
    }


def mobilization_context_from_company_state(
    state: CompanyState,
    template: MobilizationContext,
) -> CompanyMobilizeSeed:
    """Map only Q090's public availability adapter into MOBILIZE.

    Total employees and owned vehicles are never read or substituted here.
    """
    basis = mobilize_inputs(state)
    blockers: list[str] = []
    workers = basis["workers"]
    vehicles = basis["own_vehicles_available"]
    if workers["state"] != "KNOWN":
        blockers.append("COMPANY_AVAILABLE_CREW_UNKNOWN")
        return CompanyMobilizeSeed(None, basis, tuple(blockers))
    count = workers["value"]
    if isinstance(count, bool) or not isinstance(count, int):
        blockers.append("COMPANY_AVAILABLE_CREW_INVALID")
        return CompanyMobilizeSeed(None, basis, tuple(blockers))
    if count <= 0:
        blockers.append("COMPANY_AVAILABLE_CREW_ZERO")
        return CompanyMobilizeSeed(None, basis, tuple(blockers))

    own_vehicles: int | None = None
    if vehicles["state"] == "KNOWN":
        value = vehicles["value"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            blockers.append("COMPANY_AVAILABLE_VEHICLES_INVALID")
            return CompanyMobilizeSeed(None, basis, tuple(blockers))
        own_vehicles = value
    elif vehicles["state"] == "CONFLICT":
        blockers.append("COMPANY_AVAILABLE_VEHICLES_CONFLICT")
    else:
        blockers.append("COMPANY_AVAILABLE_VEHICLES_UNKNOWN")

    return CompanyMobilizeSeed(
        replace(template, workers=count, own_vehicles_available=own_vehicles),
        basis,
        tuple(blockers),
    )


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
    probable = _probable_bid_result(bid)
    execution_known, execution_complete, bangs_unknowns, bangs_warnings, bangs_bases = _bangs_execution(bangs)
    selected_mobilization = (
        MoneyView.from_amount(mobilization.probable_cost, mobilization.currency)
        if mobilization is not None and mobilization.probable_cost is not None
        else None
    )

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
        "scope_note": "Bid Economics values are authoritative only within its supplied cost-component scope; no combined profit is manufactured here.",
    }

    cash_only = _cash_only_lines(cash_assessments)
    cash_exposure = {
        "working_capital_requirement": _money_dict(probable.working_capital_requirement),
        "guarantee_amount": _money_dict(bid.bonding_exposure),
        "guarantee_fees": _money_dict(bid.bonding_fees),
        "field_cash_only": list(cash_only),
        "note": "deposit/cash-only amounts are cash exposure, not economic cost; guarantee amount is not guarantee fee",
    }

    unknowns: list[str] = [f"bid:{item}" for item in bid.missing_inputs]
    warnings: list[str] = [f"bid:{item}" for item in bid.warnings]
    blockers: list[str] = []
    assumptions: list[str] = [f"bid:{item}" for item in bid.assumptions]
    source_basis: list[str] = [f"bid:{bid.assessment_version}"]
    scenario_basis: list[str] = [item.scenario.value for item in bid.scenarios]

    if bangs is None:
        unknowns.append("bangs:execution_cost")
    else:
        unknowns.extend(bangs_unknowns)
        warnings.extend(bangs_warnings)
        source_basis.extend(f"bangs-cost-basis:{item}" for item in bangs_bases)
        if not execution_complete:
            blockers.append("EXECUTION_COST_PARTIAL")

    if mobilization is None:
        unknowns.append("mobilize:assessment")
    else:
        unknowns.extend(f"mobilize:{item}" for item in mobilization.missing_inputs)
        warnings.extend(f"mobilize:{item}" for item in mobilization.warnings)
        assumptions.extend(f"mobilize:{item}" for item in mobilization.assumptions)
        source_basis.append(f"mobilize:{mobilization.contract_version}:{mobilization.policy_version}")
        scenario_basis.extend(item.scenario for item in mobilization.alternative_scenarios)
        if mobilization.recommended_scenario == "NO CLEAR WINNER" or mobilization.probable_cost is None:
            blockers.append("MOBILIZATION_NO_DEFENSIBLE_SCENARIO")

    if probable.execution_cost is None or bid.revenue.money is None:
        blockers.append("BID_ECONOMICS_INCOMPLETE")

    if selected_mobilization is not None and probable.execution_cost is not None and reconciliation.mobilization_in_bid_execution_cost is None:
        blockers.append("MOBILIZATION_BID_SCOPE_UNRECONCILED")
    if execution_known is not None and probable.execution_cost is not None and reconciliation.bangs_execution_in_bid_execution_cost is None:
        blockers.append("BANGS_BID_SCOPE_UNRECONCILED")
    if selected_mobilization is not None and execution_known is not None:
        warnings.append("NO_AUTOMATIC_BANGS_MOBILIZE_SUM: scopes may overlap")
    if probable.gross_profit is not None and (selected_mobilization is not None or execution_known is not None):
        warnings.append("NO_COMBINED_PROFIT: Bid gross profit is not adjusted by composition")

    company_basis: dict[str, Any] = {}
    if company_state is not None:
        company_basis = company_state_execution_basis(company_state)
        source_basis.append(f"company-state:{company_state.contract_version}:{company_state.fingerprint}")
        mob = company_basis["mobilize"]
        for key in ("workers", "own_vehicles_available", "base_location"):
            if mob[key]["state"] != "KNOWN":
                unknowns.append(f"company_state:mobilize:{key}")
        constraints = company_basis["economics_constraints"]
        for key, value in constraints.items():
            if key in {"account_id", "company_state_fingerprint"}:
                continue
            if value["state"] != "KNOWN":
                unknowns.append(f"company_state:economics:{key}")

    essential = frozenset(str(item) for item in essential_providers)
    provider_views: list[ProviderAvailabilityView] = []
    for name, result in sorted((provider_results or {}).items()):
        view = _provider_view(name, result, essential=name in essential)
        provider_views.append(view)
        source_basis.append(f"provider:{name}:{view.owner_status}")
        if view.state is not ProviderAvailability.AVAILABLE:
            unknowns.append(f"provider:{name}")
            if view.essential:
                blockers.append(f"ESSENTIAL_PROVIDER_{view.state.value}:{name}")

    currencies: set[str] = {bid.currency}
    for money in (selected_mobilization, execution_known):
        if money is not None:
            currencies.add(money.currency)
    for money in (probable.working_capital_requirement, bid.bonding_exposure, bid.bonding_fees):
        if money is not None:
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
        opportunity_id=opportunity,
        tenant_id=tenant,
        contract_version=CONTRACT_VERSION,
        currency_state=currency_state,
        currencies=tuple(sorted(currencies)),
        known_bid_economics=bid_view,
        known_mobilization_cost=selected_mobilization,
        known_execution_cost=execution_known,
        execution_cost_complete=execution_complete,
        cash_exposure=cash_exposure,
        mobilization_options=_mobilization_options(mobilization),
        company_state_basis=company_basis,
        provider_availability=tuple(provider_views),
        scenario_basis=tuple(dict.fromkeys(scenario_basis)),
        source_basis=tuple(dict.fromkeys(source_basis)),
        unknown_components=tuple(dict.fromkeys(unknowns)),
        assumptions=tuple(dict.fromkeys(assumptions)),
        warnings=tuple(dict.fromkeys(warnings)),
        blockers=tuple(dict.fromkeys(blockers)),
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
    """Deterministic bounded what-if delegated to MOBILIZE; no forecasting."""
    revised_context = context
    revised_policy = policy
    if distance_km_one_way is not None:
        revised_context = replace(
            revised_context,
            distance_km_one_way=RangeInput.scalar(
                distance_km_one_way,
                quality="ESTIMATED",
                source="what-if override: distance_km_one_way",
            ),
        )
    if crew_size is not None:
        revised_context = replace(revised_context, workers=crew_size)
    if working_days is not None:
        revised_context = replace(revised_context, working_days=working_days)
    if hotel_available is not None:
        revised_context = replace(revised_context, hotel_available=hotel_available)
    if hotel_rate is not None:
        revised_policy = replace(
            revised_policy,
            accommodation_per_worker_night=RangeInput.scalar(
                hotel_rate,
                quality="ESTIMATED",
                source="what-if override: hotel_rate",
            ),
        )
    return Mobilize.evaluate(revised_context, revised_policy)
