from datetime import datetime, timezone
from decimal import Decimal
import pytest

from bangs.comparator import ComparisonStatus, CostOption, Objective, compare_cost_options
from bangs.contracts import CompanyContext, ProjectLocation
from bangs.costs import CostBasis, CostLine, assess_cost_lines
from bangs.evidence import Availability, ConfirmationState, EvidenceBasis, SourceEvidence, Visibility
from bangs.field_expenses import FieldExpenseInput, FieldExpenseKind, assess_field_expenses, per_diem_expense
from bangs.mobilization import compose_mobilization
from bangs.money import Money
from bangs.providers.base import ProviderQueryContext, ProviderResult, ProviderStatus, safe_provider_query
from bangs.scenarios import assess_scenarios
from bangs.tenant import ScopedObservation, TenantObservationStore
from bangs.true_cost import JobCostCategory, JobCostContribution, assess_true_job_cost

NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)
EV = SourceEvidence("x", EvidenceBasis.USER_INPUT, NOW)

def cost(value, currency="EUR", unknown=()):
    return assess_cost_lines((CostLine("x", Money.of(value, currency), CostBasis.ASSUMPTION, EV),), unknown_components=unknown)

def test_field_expense_per_diem_uses_company_input_not_universal_rate():
    pd = per_diem_expense(rate_per_person_day=Money.of(25, "EUR"), crew_size=10, days=5)
    a = assess_field_expenses((pd,))
    assert a.known_total.amount == 1250

def test_missing_required_field_expense_is_unknown():
    a = assess_field_expenses((), required_kinds=(FieldExpenseKind.PER_DIEM,))
    assert a.known_total is None
    assert "per_diem" in a.unknown_components

def test_mobilization_and_demobilization_are_separate():
    m = compose_mobilization(
        crew_travel=CostLine("crew_travel", Money.of(1000, "EUR"), CostBasis.ESTIMATE),
        demobilization_lines=(CostLine("return", Money.of(700, "EUR"), CostBasis.ESTIMATE),),
    )
    assert m.mobilization.known_total.amount == 1000
    assert m.demobilization.known_total.amount == 700

def test_true_job_cost_complete_and_partial_semantics():
    complete = assess_true_job_cost((
        JobCostContribution(JobCostCategory.MATERIAL_LANDED_COST, cost(600)),
        JobCostContribution(JobCostCategory.EQUIPMENT_COST, cost(100)),
    ))
    assert complete.total_job_cost_known
    assert complete.assessment.known_total.amount == 700
    partial = assess_true_job_cost((
        JobCostContribution(JobCostCategory.DIRECT_KNOWN_COST, cost(900000)),
        JobCostContribution(JobCostCategory.MATERIAL_LANDED_COST, cost(0, unknown=("unpriced_materials",))),
    ))
    assert partial.assessment.known_total.amount == 900000
    assert not partial.total_job_cost_known
    assert partial.assessment.unknown_components

def test_true_job_cost_multi_currency_unresolved():
    mixed = assess_true_job_cost((
        JobCostContribution(JobCostCategory.MATERIAL_LANDED_COST, cost(100, "EUR")),
        JobCostContribution(JobCostCategory.EQUIPMENT_COST, cost(100, "PLN")),
    ))
    assert mixed.assessment.known_total is None
    assert "MULTI_CURRENCY_UNRESOLVED" in mixed.assessment.warnings

def test_scenarios_are_independent_deterministic_aggregations():
    minc=(JobCostContribution(JobCostCategory.OTHER, cost(100)),)
    prob=(JobCostContribution(JobCostCategory.OTHER, cost(120)),)
    prud=(JobCostContribution(JobCostCategory.OTHER, cost(150)),)
    s=assess_scenarios(minimum=minc, probable=prob, prudent=prud)
    assert [s.minimum.assessment.known_total.amount, s.probable.assessment.known_total.amount, s.prudent.assessment.known_total.amount] == [100,120,150]

def test_comparator_excludes_unavailable_cheapest():
    options=(
        CostOption("cheap", cost(50), Availability.UNAVAILABLE, ConfirmationState.AVAILABILITY_CONFIRMED, "same"),
        CostOption("valid", cost(60), Availability.AVAILABLE, ConfirmationState.AVAILABILITY_CONFIRMED, "same"),
    )
    r=compare_cost_options(options)
    assert r.winner_id == "valid"
    assert r.status is ComparisonStatus.CONFIRMED_BEST_OBSERVED

def test_comparator_never_calls_unknown_availability_confirmed_best():
    r=compare_cost_options((CostOption("a", cost(50), Availability.UNKNOWN, ConfirmationState.AVAILABILITY_UNKNOWN, "same"), CostOption("b", cost(60), Availability.AVAILABLE, ConfirmationState.AVAILABILITY_CONFIRMED, "same")))
    assert r.winner_id == "a"
    assert r.status is ComparisonStatus.LOWEST_OBSERVED_AVAILABILITY_UNKNOWN

def test_comparator_requires_equivalence_and_same_currency():
    mismatch=compare_cost_options((CostOption("a", cost(50), equivalence_key="grade-A"), CostOption("b", cost(40), equivalence_key="grade-B")))
    assert mismatch.status is ComparisonStatus.NO_COMPARABLE_WINNER
    mixed=compare_cost_options((CostOption("a", cost(50,"EUR"), equivalence_key="same"), CostOption("b", cost(40,"PLN"), equivalence_key="same")))
    assert mixed.status is ComparisonStatus.MULTI_CURRENCY_UNRESOLVED

def test_lowest_known_cost_savings_are_auditable():
    r=compare_cost_options((CostOption("a", cost(500), Availability.AVAILABLE, ConfirmationState.AVAILABILITY_CONFIRMED, "same"), CostOption("b", cost(550), Availability.AVAILABLE, ConfirmationState.AVAILABILITY_CONFIRMED, "same")))
    assert r.winner_id == "a"
    assert r.savings_vs_next.amount == 50


def test_comparator_never_confirms_partial_known_subtotal_as_best():
    partial = assess_cost_lines((CostLine("known", Money.of(40, "EUR"), CostBasis.ESTIMATE),), unknown_components=("delivery",))
    complete = cost(50)
    result = compare_cost_options((
        CostOption("partial", partial, Availability.AVAILABLE, ConfirmationState.AVAILABILITY_CONFIRMED, "same"),
        CostOption("complete", complete, Availability.AVAILABLE, ConfirmationState.AVAILABILITY_CONFIRMED, "same"),
    ))
    assert result.winner_id == "partial"
    assert result.status is ComparisonStatus.LOWEST_KNOWN_PARTIAL
    assert result.savings_vs_next is None
    assert "UNKNOWN_COST_COMPONENTS" in result.notes

def test_tenant_store_prevents_cross_tenant_reads_and_shares_public_observations():
    store=TenantObservationStore[str]()
    store.put(ScopedObservation("public", "catalogue", Visibility.PUBLIC, None))
    store.put(ScopedObservation("private", "A quote", Visibility.TENANT_PRIVATE, "A"))
    assert store.get("private", tenant_id="A") == "A quote"
    assert store.get("private", tenant_id="B") is None
    assert store.get("public", tenant_id="B") == "catalogue"
    assert store.list_visible(tenant_id="B") == ("catalogue",)

def test_tenant_store_is_idempotent_but_rejects_id_collision():
    store=TenantObservationStore[str]()
    x=ScopedObservation("x", "same", Visibility.TENANT_PRIVATE, "A")
    store.put(x); store.put(x)
    with pytest.raises(ValueError): store.put(ScopedObservation("x", "different", Visibility.TENANT_PRIVATE, "A"))

class BoomProvider:
    provider_name="boom"
    def query(self, query, context): raise RuntimeError("500")
class TimeoutProvider:
    provider_name="timeout"
    def query(self, query, context): raise TimeoutError()
class TooManyProvider:
    provider_name="many"
    def query(self, query, context): return ProviderResult(ProviderStatus.OK, tuple(range(100)))

def test_provider_failures_never_translate_into_zero_price():
    ctx=ProviderQueryContext(timeout_seconds=1, max_results=5)
    assert safe_provider_query(BoomProvider(), None, ctx).status is ProviderStatus.UNAVAILABLE
    assert safe_provider_query(TimeoutProvider(), None, ctx).status is ProviderStatus.TIMEOUT
    bounded=safe_provider_query(TooManyProvider(), None, ctx)
    assert bounded.status is ProviderStatus.OK and len(bounded.items)==5

def test_provider_context_is_bounded():
    with pytest.raises(ValueError): ProviderQueryContext(timeout_seconds=0)
    with pytest.raises(ValueError): ProviderQueryContext(max_results=1000)

def test_structured_geography_rejects_malformed_coordinates():
    p=ProjectLocation("site", country_code="pt", latitude=39.7, longitude=-8.8)
    assert p.country_code == "PT"
    with pytest.raises(ValueError): ProjectLocation("bad", latitude=100, longitude=0)
    with pytest.raises(ValueError): ProjectLocation("half", latitude=10)

def test_company_context_is_optional_and_not_parallel_company_state():
    c=CompanyContext("tenant-A", base_location=ProjectLocation("Leiria", country_code="PT"), fuel_consumption_l_per_100km=8)
    assert c.tenant_id == "tenant-A"


def test_positive_cost_monotonicity_and_determinism():
    base = cost(100)
    higher = assess_cost_lines((*base.lines, CostLine("extra", Money.of(1, "EUR"), CostBasis.FACT)))
    assert higher.known_total.amount >= base.known_total.amount
    assert assess_true_job_cost((JobCostContribution(JobCostCategory.OTHER, base),)) == assess_true_job_cost((JobCostContribution(JobCostCategory.OTHER, base),))


def test_more_identical_costed_trips_cannot_reduce_route_cost():
    from bangs.routes import RouteFacts, DistanceBasis, FuelObservation, VehicleEconomics, RouteDirection, assess_route_cost
    r = RouteFacts(100, 60, DistanceBasis.USER_INPUT)
    v = VehicleEconomics(10, FuelObservation(Money.of(2, "EUR"), None, EV))
    one = assess_route_cost(r, v, direction=RouteDirection.ROUND_TRIP, number_of_trips=1, tolls_known=True)
    two = assess_route_cost(r, v, direction=RouteDirection.ROUND_TRIP, number_of_trips=2, tolls_known=True)
    assert two.assessment.known_total.amount == one.assessment.known_total.amount * 2


def test_oversized_project_and_tenant_context_inputs_are_rejected():
    from bangs.contracts import CompanyContext, ProjectLocation
    with pytest.raises(ValueError):
        ProjectLocation("x" * 301)
    with pytest.raises(ValueError):
        CompanyContext("t" * 129)
