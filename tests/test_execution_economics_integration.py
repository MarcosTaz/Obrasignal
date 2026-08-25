from datetime import datetime, timezone
from decimal import Decimal

import pytest

from bangs.accommodation import AccommodationCandidate, AccommodationType, RateBasis, assess_accommodation
from bangs.costs import CostBasis, CostLine, assess_cost_lines
from bangs.equipment import EquipmentMode, EquipmentOption, RentalRateBasis, assess_equipment
from bangs.evidence import Availability, ConfirmationState, EvidenceBasis, RequirementBasis, SourceEvidence, TaxBasis, Visibility
from bangs.materials import MaterialPriceObservation, MaterialRequirement
from bangs.money import Money as BangsMoney
from bangs.providers.base import ProviderResult, ProviderStatus
from bangs.tenant import ScopedObservation, TenantObservationStore
from bangs.true_cost import TrueJobCostAssessment
from bid_economics import (
    BidEconomicsInput,
    CostCategory,
    CostComponent,
    CostNature,
    EconomicValue,
    GuaranteeExposure,
    InputBasis,
    Money as BidMoney,
    PaymentTerm,
    PaymentTerms,
    RevenueBasis,
    ScenarioMoney,
    evaluate_bid_economics,
)
from company_state import CompanyFact, CompanyState, FactCategory, KnowledgeState, Money as StateMoney
from execution_economics import (
    CurrencyState,
    MoneyView,
    ScopeReconciliation,
    compose_execution_economics,
    mobilization_context_from_company_state,
    recompute_mobilization_what_if,
)
from mobilize import MobilizationContext, Mobilize, MobilizePolicy, RangeInput

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def r(value, quality="QUOTED"):
    return RangeInput.scalar(value, quality=quality, source="execution integration fixture")


def mobilize_context(**overrides):
    values = dict(
        workers=4,
        working_days=20,
        distance_km_one_way=r(50),
        travel_hours_one_way=r("0.75"),
        vehicle_seats=4,
        own_vehicles_available=1,
        rental_available=True,
        hotel_available=True,
        currency="EUR",
    )
    values.update(overrides)
    return MobilizationContext(**values)


def mobilize_policy(**overrides):
    values = dict(
        currency="EUR",
        fuel_price_per_litre=r("1.80"),
        own_vehicle_consumption_l_per_100km=r("8"),
        own_vehicle_cost_per_km=r("0.12"),
        rental_vehicle_daily_cost=r("70"),
        rental_vehicle_consumption_l_per_100km=r("8"),
        tolls_per_vehicle_round_trip=r("2"),
        parking_per_vehicle_workday=r("0"),
        accommodation_per_worker_night=r("60"),
        per_diem_per_worker_day=r("0"),
        productive_hour_value_per_worker=r("0"),
    )
    values.update(overrides)
    return MobilizePolicy(**values)


def bid_assessment(*, currency="EUR", include_unknown=False):
    known = CostComponent(
        category=CostCategory.LABOUR,
        nature=CostNature.DIRECT,
        amounts=ScenarioMoney(
            BidMoney(Decimal("380"), currency),
            BidMoney(Decimal("400"), currency),
            BidMoney(Decimal("450"), currency),
        ),
        basis=InputBasis.ESTIMATE,
        source="fixture labour estimate",
    )
    components = [known]
    if include_unknown:
        components.append(CostComponent(
            category=CostCategory.MATERIAL,
            nature=CostNature.DIRECT,
            amounts=None,
            basis=InputBasis.UNKNOWN,
            source="not priced",
        ))
    return evaluate_bid_economics(BidEconomicsInput(
        opportunity_id="opp-1",
        tenant_id="tenant-a",
        currency=currency,
        revenue=EconomicValue(BidMoney(Decimal("1000"), currency), InputBasis.FACT, "bid price"),
        revenue_basis=RevenueBasis.BID_PRICE,
        cost_components=tuple(components),
        guarantees=(GuaranteeExposure(
            "performance",
            EconomicValue(BidMoney(Decimal("100"), currency), InputBasis.FACT, "tender"),
            EconomicValue(BidMoney(Decimal("5"), currency), InputBasis.ESTIMATE, "bank indication"),
        ),),
        payment_terms=PaymentTerms(PaymentTerm.NET30),
        duration_months=Decimal("2"),
    ), generated_at=NOW)


def bangs_job(amount="250", currency="EUR", *, unknowns=()):
    assessment = assess_cost_lines(
        (CostLine("known_execution", BangsMoney.of(amount, currency), CostBasis.QUOTE),),
        unknown_components=unknowns,
    )
    return TrueJobCostAssessment(assessment, (), not bool(unknowns))


def evidence():
    return SourceEvidence("fixture", EvidenceBasis.SUPPLIER_QUOTE, NOW, source_ref="fixture-1")


def compose(*, bid=None, mobilization=None, bangs=None, **kwargs):
    return compose_execution_economics(
        tenant_id="tenant-a",
        opportunity_id="opp-1",
        bid=bid or bid_assessment(),
        mobilization=mobilization,
        bangs=bangs,
        **kwargs,
    )


def test_hotel_availability_unknown_is_not_promoted_to_selected_cost():
    mobilization = Mobilize.evaluate(mobilize_context(hotel_available=None), mobilize_policy())
    result = compose(mobilization=mobilization, bangs=bangs_job())
    stays = [item for item in result.mobilization_options if item["strategy"] != "DAILY_COMMUTE"]
    assert stays and all(item["availability"] == "UNKNOWN" for item in stays)
    assert result.known_mobilization_cost is None
    assert "MOBILIZATION_NO_DEFENSIBLE_SCENARIO" in result.blockers
    assert "mobilize:hotel_available" in result.unknown_components


def test_hotel_rate_basis_absent_remains_unknown_in_bangs():
    candidate = AccommodationCandidate(
        "h1", "Observed hotel", AccommodationType.HOTEL,
        BangsMoney.of("60", "EUR"), RateBasis.UNKNOWN, None, evidence(),
        confirmation=ConfirmationState.PRICE_OBSERVED,
    )
    assessed = assess_accommodation(candidate, crew_size=4, nights=5, now=NOW)
    assert assessed.assessment.known_total is None
    assert "rate_basis" in assessed.assessment.unknown_components
    assert "PRICE_OBSERVED_NOT_CONFIRMED_BOOKING" in assessed.assessment.warnings


def test_material_quantity_without_unit_is_rejected():
    with pytest.raises(ValueError, match="requires a unit"):
        MaterialRequirement("m1", "cement", Decimal("10"), None, RequirementBasis.BOQ_EXPLICIT)


def test_currency_mismatch_is_unresolved_without_fx_or_arithmetic():
    result = compose(
        mobilization=Mobilize.evaluate(mobilize_context(), mobilize_policy()),
        bangs=bangs_job(currency="PLN"),
    )
    assert result.currency_state is CurrencyState.UNRESOLVED
    assert result.currencies == ("EUR", "PLN")
    assert "MULTI_CURRENCY_UNRESOLVED" in result.blockers
    assert "NO_FX_APPLIED" in result.warnings
    assert result.known_execution_cost.currency == "PLN"


def test_unknown_fuel_blocks_mobilization_selection():
    mobilization = Mobilize.evaluate(
        mobilize_context(), mobilize_policy(fuel_price_per_litre=RangeInput())
    )
    result = compose(mobilization=mobilization, bangs=bangs_job())
    assert result.known_mobilization_cost is None
    assert "MOBILIZATION_NO_DEFENSIBLE_SCENARIO" in result.blockers
    assert "mobilize:fuel_price_per_litre" in result.unknown_components


def test_unknown_tolls_are_visible_not_zero():
    mobilization = Mobilize.evaluate(
        mobilize_context(), mobilize_policy(tolls_per_vehicle_round_trip=RangeInput())
    )
    result = compose(mobilization=mobilization, bangs=bangs_job())
    assert "mobilize:tolls_per_vehicle_round_trip" in result.unknown_components
    assert any("excludes unknown components" in item for item in mobilization.warnings)


def company_state(*, available_workers="absent", available_vehicles="absent"):
    facts = [
        CompanyFact(FactCategory.CAPACITY, "crew.total_count", KnowledgeState.FACT, 10, unit="workers"),
        CompanyFact(FactCategory.EQUIPMENT, "vehicle.owned_count", KnowledgeState.FACT, 3, unit="vehicles"),
        CompanyFact(FactCategory.GEOGRAPHY, "geography.base", KnowledgeState.FACT, "Leiria, PT"),
        CompanyFact(FactCategory.FINANCIAL_CONSTRAINT, "finance.working_capital_limit", KnowledgeState.FACT, StateMoney(Decimal("5000"), "EUR")),
    ]
    if available_workers != "absent":
        facts.append(CompanyFact(
            FactCategory.AVAILABILITY, "crew.available_count",
            KnowledgeState.UNKNOWN if available_workers is None else KnowledgeState.FACT,
            None if available_workers is None else available_workers, unit="workers",
        ))
    if available_vehicles != "absent":
        facts.append(CompanyFact(
            FactCategory.AVAILABILITY, "vehicle.available_count",
            KnowledgeState.UNKNOWN if available_vehicles is None else KnowledgeState.FACT,
            None if available_vehicles is None else available_vehicles, unit="vehicles",
        ))
    return CompanyState("tenant-a", NOW, tuple(facts))


def test_total_workers_and_owned_vehicles_do_not_become_available_resources():
    state = company_state()
    seed = mobilization_context_from_company_state(state, mobilize_context())
    assert seed.context is None
    assert "COMPANY_AVAILABLE_CREW_UNKNOWN" in seed.blockers
    assert seed.basis["workers"]["state"] == "UNKNOWN"
    assert seed.basis["own_vehicles_available"]["state"] == "UNKNOWN"


def test_zero_available_workers_is_known_zero_but_not_executable_crew():
    seed = mobilization_context_from_company_state(
        company_state(available_workers=0, available_vehicles=1), mobilize_context()
    )
    assert seed.context is None
    assert seed.basis["workers"]["state"] == "KNOWN"
    assert seed.basis["workers"]["value"] == 0
    assert "COMPANY_AVAILABLE_CREW_ZERO" in seed.blockers


def test_known_available_crew_and_vehicle_seed_mobilize_without_total_substitution():
    seed = mobilization_context_from_company_state(
        company_state(available_workers=6, available_vehicles=1),
        mobilize_context(workers=99, own_vehicles_available=99),
    )
    assert seed.context is not None
    assert seed.context.workers == 6
    assert seed.context.own_vehicles_available == 1


def test_provider_unavailable_and_timeout_never_become_zero_success():
    result = compose(
        bangs=bangs_job(),
        provider_results={
            "hotel": ProviderResult(status=ProviderStatus.UNAVAILABLE, error_code="down"),
            "route": ProviderResult(status=ProviderStatus.TIMEOUT, error_code="timeout"),
        },
        essential_providers={"hotel", "route"},
    )
    states = {item.provider: item.state.value for item in result.provider_availability}
    assert states == {"hotel": "UNAVAILABLE", "route": "ERROR"}
    assert "ESSENTIAL_PROVIDER_UNAVAILABLE:hotel" in result.blockers
    assert "ESSENTIAL_PROVIDER_ERROR:route" in result.blockers
    assert result.to_dict()["provider_availability"][0].get("amount") is None


def test_partial_known_execution_cost_is_subtotal_not_total():
    result = compose(bangs=bangs_job(unknowns=("materials", "equipment")))
    assert result.known_execution_cost.amount == Decimal("250")
    assert result.execution_cost_complete is False
    assert "bangs:materials" in result.unknown_components
    assert "bangs:equipment" in result.unknown_components
    assert "EXECUTION_COST_PARTIAL" in result.blockers
    assert result.read_model["KNOWN COSTS"][0]["is_total"] is False


def test_deposit_is_cash_exposure_not_execution_economic_cost():
    equipment = assess_equipment(EquipmentOption(
        "eq1", "lift", EquipmentMode.RENT, 1,
        BangsMoney.of("50", "EUR"), RentalRateBasis.DAILY, Decimal("1"),
        Availability.AVAILABLE, evidence(), deposit=BangsMoney.of("100", "EUR"),
    ))
    job = TrueJobCostAssessment(equipment.economic, (), True)
    result = compose(bangs=job, cash_assessments=(equipment.cash_outlay,))
    assert result.known_execution_cost.amount == Decimal("50")
    deposit = result.cash_exposure["field_cash_only"][0]
    assert deposit["code"] == "deposit"
    assert deposit["amount"] == {"amount": "100", "currency": "EUR"}


def test_guarantee_amount_and_fee_remain_separate():
    result = compose(bangs=bangs_job())
    assert result.cash_exposure["guarantee_amount"] == {"amount": "100", "currency": "EUR"}
    assert result.cash_exposure["guarantee_fees"] == {"amount": "5", "currency": "EUR"}
    assert result.cash_exposure["guarantee_amount"] != result.cash_exposure["guarantee_fees"]


def test_no_combined_true_profit_is_manufactured_across_owner_scopes():
    result = compose(
        mobilization=Mobilize.evaluate(mobilize_context(), mobilize_policy()),
        bangs=bangs_job(),
        reconciliation=ScopeReconciliation(False, False),
    )
    payload = result.to_dict()
    assert "true_profit" not in payload
    assert "combined_profit" not in payload
    assert payload["known_bid_economics"]["probable_gross_profit"] == {"amount": "600", "currency": "EUR"}
    assert "NO_COMBINED_PROFIT: Bid gross profit is not adjusted by composition" in result.warnings
    assert "NO_AUTOMATIC_BANGS_MOBILIZE_SUM: scopes may overlap" in result.warnings


def test_unreconciled_owner_cost_scopes_block_false_profit_certainty():
    result = compose(
        mobilization=Mobilize.evaluate(mobilize_context(), mobilize_policy()),
        bangs=bangs_job(),
    )
    assert "MOBILIZATION_BID_SCOPE_UNRECONCILED" in result.blockers
    assert "BANGS_BID_SCOPE_UNRECONCILED" in result.blockers


def test_extreme_decimal_precision_and_nonfinite_rejected_at_composition_boundary():
    value = Decimal(2) ** 53 + Decimal("0.0000000000000001")
    view = MoneyView(value, "EUR")
    assert view.to_dict()["amount"].endswith("0000000000000001")
    for bad in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        with pytest.raises(ValueError, match="finite"):
            MoneyView(bad, "EUR")


def test_private_quote_cannot_cross_tenant_boundary():
    quote = MaterialPriceObservation(
        "q1", "m1", "supplier-1", "kg", BangsMoney.of("2.50", "EUR"),
        TaxBasis.TAX_UNKNOWN, evidence(), Visibility.TENANT_PRIVATE,
        tenant_id="tenant-a", availability=Availability.UNKNOWN,
    )
    store = TenantObservationStore[MaterialPriceObservation]()
    store.put(ScopedObservation("q1", quote, Visibility.TENANT_PRIVATE, "tenant-a"))
    assert store.get("q1", tenant_id="tenant-a") == quote
    assert store.get("q1", tenant_id="tenant-b") is None
    assert store.list_visible(tenant_id="tenant-b") == ()


def test_company_state_cross_tenant_composition_fails_closed():
    other = company_state(available_workers=4, available_vehicles=1)
    other = CompanyState("tenant-b", other.as_of, other.facts)
    with pytest.raises(ValueError, match="TENANT_MISMATCH: company state"):
        compose_execution_economics(
            tenant_id="tenant-a",
            opportunity_id="opp-1",
            bid=bid_assessment(),
            company_state=other,
        )


def test_read_model_has_required_executive_sections():
    result = compose(
        mobilization=Mobilize.evaluate(mobilize_context(), mobilize_policy()),
        bangs=bangs_job(),
        company_state=company_state(available_workers=4, available_vehicles=1),
    )
    assert set(result.read_model) >= {
        "KNOWN COSTS", "ESTIMATED COSTS", "ASSUMPTIONS", "UNKNOWN COSTS",
        "CASH EXPOSURE", "MOBILIZATION OPTIONS", "SOURCE/EVIDENCE BASIS",
    }
    assert result.company_state_basis["mobilize"]["workers"]["value"] == 4
    assert result.company_state_basis["economics_constraints"]["working_capital_limit"]["value"] == {"amount": "5000", "currency": "EUR"}


def test_what_if_is_deterministic_and_delegates_to_mobilize():
    context = mobilize_context()
    policy = mobilize_policy()
    one = recompute_mobilization_what_if(
        context, policy,
        hotel_rate="25.125", distance_km_one_way="120.5", crew_size=8, working_days=30,
    )
    two = recompute_mobilization_what_if(
        context, policy,
        hotel_rate="25.125", distance_km_one_way="120.5", crew_size=8, working_days=30,
    )
    assert one.to_dict() == two.to_dict()
    assert all(item.metrics["workers"] == 8 for item in one.alternative_scenarios)
    assert any("what-if override" in (item.get("source") or "") for item in one.evidence)
