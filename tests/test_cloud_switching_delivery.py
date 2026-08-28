from decimal import Decimal

from cloud_switching.baseline import BaselineCost, Certainty, CurrentStateBaseline
from cloud_switching.comparability import ObservationWindow
from cloud_switching.delivery import build_delivery
from cloud_switching.incentives import Incentive, IncentiveStatus
from cloud_switching.options import OptionType, SwitchingOption
from cloud_switching.outcome import Evidence, EvidenceStrength, ForecastActual, MigrationOutcomeRecord
from cloud_switching.service import build_decision_package
from cloud_switching.synthetic import synthetic_companies

D = Decimal


def decision_package():
    case = synthetic_companies()["alpha_manufacturing_eu"].case
    baseline = CurrentStateBaseline(
        company_id="tenant-a",
        components=[BaselineCost("current", case.current_annual_cost, Certainty.KNOWN, source_id="billing")],
    )
    incentives = [
        Incentive(
            incentive_id="provider",
            program="Provider funding",
            status=IncentiveStatus.PARTIALLY_RECEIVED,
            approved_amount=case.provider_credit_approved,
            received_amount=case.provider_credit_received,
            approval_evidence_id="provider-approval",
            receipt_evidence_id="provider-receipt",
        ),
        Incentive(
            incentive_id="partner",
            program="Partner funding",
            status=IncentiveStatus.PARTIALLY_RECEIVED,
            approved_amount=case.partner_incentive_approved,
            received_amount=case.partner_incentive_received,
            approval_evidence_id="partner-approval",
            receipt_evidence_id="partner-receipt",
        ),
    ]
    return build_decision_package(baseline, case, incentives)


def outcome_record(*, independent=True):
    evidence = Evidence("machine", EvidenceStrength.MACHINE, independent, "v0.1")
    return MigrationOutcomeRecord(
        case_id="case-1",
        source_platform="vmware",
        destination_platform="aws",
        workload_class="vm",
        migration_strategy="rehost",
        migration_cost=ForecastActual(D("100000"), D("120000"), evidence),
        duration_days=ForecastActual(D("180"), D("240"), evidence),
        annual_run_cost=ForecastActual(D("180000"), D("200000"), evidence),
        downtime_minutes=ForecastActual(D("30"), D("90"), evidence),
        provider_incentive=ForecastActual(D("30000"), D("25000"), evidence),
    )


def options():
    return [
        SwitchingOption("renew", OptionType.RENEW, "vmware", "EUR", D("300000")),
        SwitchingOption("aws", OptionType.SWITCH, "aws", "EUR", D("180000"), D("100000"), D("30000")),
    ]


def test_delivery_contains_decision_option_winner_and_forecast_error():
    delivery = build_delivery(
        decision_package(),
        options(),
        outcome_record=outcome_record(),
        pre_run_cost=D("240000"),
        pre_window=ObservationWindow(12, D("1000000"), "gold"),
        post_window=ObservationWindow(12, D("1000000"), "gold"),
    )
    assert delivery.options.economic_winner_id == "aws"
    assert delivery.outcome is not None
    assert delivery.outcome.migration_cost_variance == D("20000")
    assert delivery.outcome.duration_variance_days == D("60")
    assert delivery.outcome.annual_run_cost_variance == D("20000")
    assert delivery.outcome.provider_incentive_variance == D("-5000")
    assert delivery.outcome.comparability_grade == "A"
    assert delivery.outcome.verified_for_benchmark


def test_non_independent_outcome_never_enters_verified_benchmark():
    delivery = build_delivery(
        decision_package(),
        options(),
        outcome_record=outcome_record(independent=False),
        pre_run_cost=D("240000"),
        pre_window=ObservationWindow(12, D("1000000"), "gold"),
        post_window=ObservationWindow(12, D("1000000"), "gold"),
    )
    assert delivery.outcome is not None
    assert not delivery.outcome.verified_for_benchmark


def test_changed_service_level_blocks_verified_benchmark_even_with_machine_evidence():
    delivery = build_delivery(
        decision_package(),
        options(),
        outcome_record=outcome_record(),
        pre_run_cost=D("240000"),
        pre_window=ObservationWindow(12, D("1000000"), "gold"),
        post_window=ObservationWindow(12, D("1000000"), "bronze"),
    )
    assert delivery.outcome is not None
    assert not delivery.outcome.comparable_run_cost
    assert not delivery.outcome.verified_for_benchmark
