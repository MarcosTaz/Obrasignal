from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .baseline import BaselineCost, Certainty, CurrentStateBaseline
from .comparability import ObservationWindow
from .delivery import EconomicAssuranceDelivery, build_delivery
from .incentives import Incentive, IncentiveStatus
from .options import OptionType, SwitchingOption
from .outcome import Evidence, EvidenceStrength, ForecastActual, MigrationOutcomeRecord
from .phased import MigrationWave, PhasedMigrationPlan, PhasedRunResult, calculate_phased_run_cost
from .service import build_decision_package
from .synthetic import synthetic_companies

D = Decimal


@dataclass(frozen=True)
class ShadowCustomerResult:
    company_id: str
    delivery: EconomicAssuranceDelivery
    phased_run: PhasedRunResult
    expected_unsubsidized_winner: str
    expected_customer_cash_winner: str


def run_alpha_shadow_customer() -> ShadowCustomerResult:
    company_id = "alpha-manufacturing-eu"
    case = synthetic_companies()["alpha_manufacturing_eu"].case

    baseline = CurrentStateBaseline(
        company_id=company_id,
        components=[
            BaselineCost("vmware_license_support", D("80000"), Certainty.KNOWN, source_id="contract-vmware-2026"),
            BaselineCost("compute_storage_network", D("110000"), Certainty.KNOWN, source_id="invoice-dc-2026"),
            BaselineCost("operations_staff", D("50000"), Certainty.ESTIMATED, source_id="finance-allocation-2026"),
        ],
    )

    incentives = [
        Incentive(
            incentive_id="provider-credit",
            program="Destination migration credit",
            status=IncentiveStatus.PARTIALLY_RECEIVED,
            potential_amount=D("30000"),
            approved_amount=D("30000"),
            received_amount=D("25000"),
            approval_evidence_id="provider-approval-1",
            receipt_evidence_id="provider-credit-memo-1",
        ),
        Incentive(
            incentive_id="partner-funding",
            program="Partner migration funding",
            status=IncentiveStatus.PARTIALLY_RECEIVED,
            potential_amount=D("10000"),
            approved_amount=D("10000"),
            received_amount=D("5000"),
            approval_evidence_id="partner-approval-1",
            receipt_evidence_id="partner-credit-memo-1",
        ),
    ]

    decision = build_decision_package(baseline, case, incentives)

    options = [
        SwitchingOption("renew-vmware", OptionType.RENEW, "vmware", "EUR", D("300000")),
        SwitchingOption("destination-a", OptionType.SWITCH, "public-cloud-a", "EUR", D("180000"), D("100000"), D("30000")),
        SwitchingOption("destination-b", OptionType.SWITCH, "alternative-virtualization", "EUR", D("188000"), D("60000"), D("5000")),
    ]

    machine = Evidence("verified-outcome-export", EvidenceStrength.MACHINE, True, "v0.1")
    outcome = MigrationOutcomeRecord(
        case_id=case.case_id,
        source_platform="vmware",
        destination_platform="public-cloud-a",
        workload_class="vm",
        migration_strategy="rehost",
        migration_cost=ForecastActual(D("100000"), D("120000"), machine),
        duration_days=ForecastActual(D("180"), D("240"), machine),
        annual_run_cost=ForecastActual(D("180000"), D("200000"), machine),
        downtime_minutes=ForecastActual(D("30"), D("90"), machine),
        provider_incentive=ForecastActual(D("30000"), D("25000"), machine),
    )

    delivery = build_delivery(
        decision,
        options,
        horizon_years=3,
        outcome_record=outcome,
        pre_run_cost=case.current_annual_cost,
        pre_window=ObservationWindow(12, D("1000000"), "gold"),
        post_window=ObservationWindow(12, D("1100000"), "gold"),
    )

    phased = calculate_phased_run_cost(
        PhasedMigrationPlan(
            source_annual_run_cost=case.current_annual_cost,
            target_annual_run_cost=case.target_annual_cost,
            waves=[
                MigrationWave(1, D("0.25")),
                MigrationWave(4, D("0.25")),
                MigrationWave(7, D("0.25")),
                MigrationWave(10, D("0.25")),
            ],
            decommission_lag_months=2,
            renewal_overlap_months=3,
            renewal_overlap_monthly_cost=D("5000"),
        ),
        12,
    )

    return ShadowCustomerResult(
        company_id=company_id,
        delivery=delivery,
        phased_run=phased,
        expected_unsubsidized_winner="destination-b",
        expected_customer_cash_winner="destination-a",
    )
