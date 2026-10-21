from datetime import datetime, timezone
from decimal import Decimal

import pytest

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
    Scenario,
    ScenarioMoney,
    evaluate_bid_economics,
)
from mobilize import MobilizationContext, Mobilize, MobilizePolicy, RangeInput
from bangs.accommodation import AccommodationCandidate, AccommodationType, RateBasis, assess_accommodation
from bangs.costs import CostBasis, CostLine, assess_cost_lines
from bangs.evidence import (
    Availability,
    ConfirmationState,
    EvidenceBasis,
    SourceEvidence,
    TaxBasis,
    Visibility,
)
from bangs.financial import FinancialExposureState, assess_financial_exposure
from bangs.materials import MaterialPriceObservation
from bangs.money import Money as BangMoney
from bangs.true_cost import JobCostCategory, JobCostContribution, assess_true_job_cost

FIXED = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
OBS = SourceEvidence("market observation", EvidenceBasis.MARKET_OBSERVATION, FIXED)


def _scenario_money(amount: str, currency: str = "EUR") -> ScenarioMoney:
    money = BidMoney(Decimal(amount), currency)
    return ScenarioMoney(money, money, money)


def test_bid_economics_unknown_cost_never_becomes_zero_or_profit():
    data = BidEconomicsInput(
        opportunity_id="GP03-ECO-1",
        tenant_id="tenant-a",
        currency="EUR",
        revenue=EconomicValue(BidMoney(Decimal("500000"), "EUR"), InputBasis.ESTIMATE, "explicit bid-price fixture"),
        revenue_basis=RevenueBasis.BID_PRICE,
        cost_components=(
            CostComponent(CostCategory.LABOUR, CostNature.DIRECT, _scenario_money("100000"), InputBasis.ESTIMATE),
            CostComponent(CostCategory.MATERIAL, CostNature.DIRECT, None, InputBasis.UNKNOWN),
        ),
        payment_terms=PaymentTerms(contractual_term=PaymentTerm.NET30),
    )

    assessment = evaluate_bid_economics(data, generated_at=FIXED)
    probable = next(item for item in assessment.scenarios if item.scenario is Scenario.PROBABLE)

    assert "COST:MATERIAL" in assessment.missing_inputs
    assert probable.execution_cost is None
    assert probable.gross_profit is None
    assert probable.gross_margin_percent is None
    assert assessment.generated_at == FIXED


def test_bid_economics_never_invents_revenue_from_opportunity_value_context():
    data = BidEconomicsInput(
        opportunity_id="GP03-ECO-2",
        tenant_id="tenant-a",
        currency="EUR",
        revenue=EconomicValue(None),
        revenue_basis=RevenueBasis.UNKNOWN,
        cost_components=(),
    )

    assessment = evaluate_bid_economics(data, generated_at=FIXED)

    assert assessment.revenue.money is None
    assert "REVENUE" in assessment.missing_inputs
    assert all(item.gross_profit is None for item in assessment.scenarios)


def test_bid_economics_guarantee_exposure_is_not_guarantee_fee():
    data = BidEconomicsInput(
        opportunity_id="GP03-ECO-3",
        tenant_id="tenant-a",
        currency="EUR",
        revenue=EconomicValue(None),
        guarantees=(
            GuaranteeExposure(
                "bid_bond",
                EconomicValue(BidMoney(Decimal("10000"), "EUR"), InputBasis.FACT),
                EconomicValue(BidMoney(Decimal("125"), "EUR"), InputBasis.ESTIMATE),
            ),
        ),
    )

    assessment = evaluate_bid_economics(data, generated_at=FIXED)

    assert assessment.bonding_exposure.amount == Decimal("10000")
    assert assessment.bonding_fees.amount == Decimal("125")
    assert assessment.bonding_exposure != assessment.bonding_fees


def test_bid_economics_mixed_currency_fails_closed():
    data = BidEconomicsInput(
        opportunity_id="GP03-ECO-4",
        tenant_id="tenant-a",
        currency="EUR",
        revenue=EconomicValue(None),
        cost_components=(
            CostComponent(CostCategory.MATERIAL, CostNature.DIRECT, _scenario_money("1000", "PLN"), InputBasis.FACT),
        ),
    )

    with pytest.raises(ValueError, match="MULTI_CURRENCY_UNRESOLVED"):
        evaluate_bid_economics(data, generated_at=FIXED)


def test_mobilize_missing_propulsion_economics_cannot_create_cheapest_route():
    context = MobilizationContext(
        workers=4,
        working_days=10,
        distance_km_one_way=RangeInput.scalar(80, quality="ESTIMATED", source="fixture route"),
        travel_hours_one_way=RangeInput.scalar(1, quality="ESTIMATED", source="fixture route"),
        own_vehicles_available=1,
        rental_available=False,
        hotel_available=False,
        currency="EUR",
    )
    policy = MobilizePolicy(
        currency="EUR",
        fuel_price_per_litre=RangeInput.scalar(1.8, quality="ESTIMATED", source="fixture"),
        own_vehicle_consumption_l_per_100km=RangeInput.scalar(8, quality="ESTIMATED", source="fixture"),
        own_vehicle_cost_per_km=RangeInput(),
    )

    assessment = Mobilize.evaluate(context, policy)

    assert assessment.recommended_scenario == "NO CLEAR WINNER"
    assert assessment.estimated_cost is None
    assert "own_vehicle_cost_per_km" in assessment.missing_inputs
    assert assessment.confidence == 0


def test_mobilize_currency_mismatch_fails_closed_without_fx():
    context = MobilizationContext(2, 5, RangeInput.scalar(10), currency="EUR")
    policy = MobilizePolicy(currency="PLN")

    with pytest.raises(ValueError, match="FX conversion is outside Mobilize V1"):
        Mobilize.evaluate(context, policy)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BUG-GP-MOBILIZE-AVAIL-001: omitted hotel availability defaults to True, "
        "so UNKNOWN can be emitted as available"
    ),
)
def test_mobilize_omitted_hotel_availability_must_not_become_available():
    context = MobilizationContext(
        workers=2,
        working_days=5,
        distance_km_one_way=RangeInput.scalar(10, quality="ESTIMATED", source="fixture route"),
        travel_hours_one_way=RangeInput.scalar(0.25, quality="ESTIMATED", source="fixture route"),
        own_vehicles_available=1,
        rental_available=False,
        currency="EUR",
    )
    policy = MobilizePolicy(
        currency="EUR",
        fuel_price_per_litre=RangeInput.scalar(1.8, source="fixture"),
        own_vehicle_consumption_l_per_100km=RangeInput.scalar(8, source="fixture"),
        own_vehicle_cost_per_km=RangeInput.scalar(0.2, source="fixture"),
        accommodation_per_worker_night=RangeInput.scalar(50, source="observed rate only"),
        tolls_per_vehicle_round_trip=RangeInput.scalar(0, source="fixture"),
        parking_per_vehicle_workday=RangeInput.scalar(0, source="fixture"),
        per_diem_per_worker_day=RangeInput.scalar(0, source="fixture"),
        productive_hour_value_per_worker=RangeInput.scalar(0, source="fixture"),
    )

    assessment = Mobilize.evaluate(context, policy)
    accommodation = [item for item in assessment.alternative_scenarios if item.strategy == "ACCOMMODATION"]

    assert accommodation
    assert all(item.available is False for item in accommodation)


def test_bangs_observed_hotel_without_rate_basis_cannot_price_crew():
    candidate = AccommodationCandidate(
        "hotel-x",
        "Observed listing",
        AccommodationType.HOTEL,
        BangMoney.of(50, "EUR"),
        RateBasis.UNKNOWN,
        None,
        OBS,
        ConfirmationState.PRICE_OBSERVED,
    )

    assessment = assess_accommodation(candidate, crew_size=8, nights=2, now=FIXED)

    assert assessment.assessment.known_total is None


def test_bangs_unknown_material_cost_keeps_partial_total_from_becoming_true_total():
    known = assess_cost_lines((CostLine("known", BangMoney.of(900000, "EUR"), CostBasis.FACT),))
    unknown = assess_cost_lines((), unknown_components=("material_cost",))
    total = assess_true_job_cost((
        JobCostContribution(JobCostCategory.DIRECT_KNOWN_COST, known),
        JobCostContribution(JobCostCategory.MATERIAL_LANDED_COST, unknown),
    ))

    assert total.assessment.known_total.amount == Decimal("900000")
    assert total.total_job_cost_known is False
    assert any(
        item == "material_cost" or item.endswith(":material_cost")
        for item in total.assessment.unknown_components
    )


def test_bangs_mixed_currency_is_not_summed():
    total = assess_true_job_cost((
        JobCostContribution(
            JobCostCategory.OTHER,
            assess_cost_lines((CostLine("eur", BangMoney.of(1, "EUR"), CostBasis.FACT),)),
        ),
        JobCostContribution(
            JobCostCategory.OTHER,
            assess_cost_lines((CostLine("pln", BangMoney.of(1, "PLN"), CostBasis.FACT),)),
        ),
    ))

    assert total.assessment.known_total is None


def test_bangs_observed_listing_does_not_default_to_available():
    observation = MaterialPriceObservation(
        "obs-1",
        "material-1",
        "supplier-1",
        "m2",
        BangMoney.of(5, "EUR"),
        TaxBasis.TAX_UNKNOWN,
        OBS,
        Visibility.PUBLIC,
    )

    assert observation.availability is Availability.UNKNOWN
    assert observation.evidence.basis is EvidenceBasis.MARKET_OBSERVATION


def test_bangs_unitless_material_observation_fails_closed():
    with pytest.raises(ValueError):
        MaterialPriceObservation(
            "obs-2",
            "material-1",
            "supplier-1",
            "",
            BangMoney.of(5, "EUR"),
            TaxBasis.TAX_UNKNOWN,
            OBS,
            Visibility.PUBLIC,
        )


def test_bangs_financial_bridge_reports_provider_unavailable_not_empty_success():
    result = assess_financial_exposure("TED:GP03", "tenant-a", None)

    assert result.state is FinancialExposureState.PROVIDER_UNAVAILABLE
    assert result.working_capital is None
    assert result.financial_cost is None
